#!/usr/bin/env python3
"""
Script de inicialización de la base de datos (Global y Tenant).
Crea esquemas, tablas dinámicas y el primer usuario administrador.
"""

import asyncio
import os
import sys
from getpass import getpass

# Asegurar que se puede importar new_app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from new_app.core.config import settings
from new_app.core.database import GlobalBase, TenantBase
from new_app.models.global_models import Tenant, User
from new_app.models.tenant_models import ProductionLine
from new_app.core.auth import hash_password

async def init_db():
    print("=========================================")
    print("   Dashboard - Inicialización de BD")
    print("=========================================")
    
    db_user = input("DB User (ej. root): ") or "root"
    db_pass = getpass("DB Password: ")
    db_host = input("DB Host (ej. localhost): ") or "localhost"
    db_port = input("DB Port (ej. 3306): ") or "3306"

    # Nombres de bases de datos
    global_db_name = "camet_global"
    tenant_company = input("Nombre de la Empresa (Tenant): ")
    tenant_db_name = input(f"Nombre de la BD del Tenant (ej. db_client_{tenant_company.lower().replace(' ', '_')}): ")

    # Usuario admin
    admin_user = input("Usuario Admin: ") or "admin"
    admin_email = input("Email Admin: ")
    admin_pass = getpass("Password Admin: ")

    # Líneas
    lines_input = input("Ingrese las líneas separadas por coma (ej. Linea 1, Linea 2): ")
    lines = [L.strip() for L in lines_input.split(",") if L.strip()]

    # Motor base (sin BD específica) para crear las BD
    base_url = f"mysql+aiomysql://{db_user}:{db_pass}@{db_host}:{db_port}"
    engine_base = create_async_engine(base_url, echo=False)

    async with engine_base.begin() as conn:
        print(f"[*] Creando bases de datos {global_db_name} y {tenant_db_name} si no existen...")
        await conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {global_db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
        await conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {tenant_db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
    
    await engine_base.dispose()

    # --------------- GLOBAL DB ---------------
    global_url = f"{base_url}/{global_db_name}"
    global_engine = create_async_engine(global_url, echo=False)

    print("[*] Generando tablas globales...")
    async with global_engine.begin() as conn:
        await conn.run_sync(GlobalBase.metadata.create_all)

    GlobalSession = sessionmaker(global_engine, class_=AsyncSession, expire_on_commit=False)
    async with GlobalSession() as session:
        # Verificar tenant
        from sqlalchemy import select
        result = await session.execute(select(Tenant).where(Tenant.company_name == tenant_company))
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            tenant = Tenant(
                company_name=tenant_company,
                config_tenant={"db_name": tenant_db_name},
                is_active=True
            )
            session.add(tenant)
            await session.commit()
            print(f"[*] Creado Tenant: {tenant_company} (ID: {tenant.tenant_id})")
        else:
            print(f"[*] Tenant {tenant_company} ya existe.")

        # Verificar admin
        result = await session.execute(select(User).where(User.username == admin_user))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                tenant_id=tenant.tenant_id,
                username=admin_user,
                email=admin_email,
                password=hash_password(admin_pass),
                role="ADMIN",
                permissions={}
            )
            session.add(user)
            await session.commit()
            print(f"[*] Creado usuario admin: {admin_user}")
        else:
            print(f"[*] Usuario {admin_user} ya existe.")

    await global_engine.dispose()

    # --------------- TENANT DB ---------------
    tenant_url = f"{base_url}/{tenant_db_name}"
    tenant_engine = create_async_engine(tenant_url, echo=False)

    print(f"[*] Generando tablas del Tenant ({tenant_db_name})...")
    async with tenant_engine.begin() as conn:
        await conn.run_sync(TenantBase.metadata.create_all)

    # Tablas dinámicas por línea
    async with tenant_engine.begin() as conn:
        for line in lines:
            safe_name = line.replace(' ', '_').lower()
            table_downtime = f"downtime_events_{safe_name}"
            table_detection = f"detection_line_{safe_name}"

            print(f"[*] Creando tablas dinámicas para línea '{line}'...")
            
            # Tabla downtime
            await conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS `{table_downtime}` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `start_time` DATETIME NOT NULL,
                    `end_time` DATETIME NULL,
                    `duration` FLOAT NULL,
                    `reason` VARCHAR(255) NULL,
                    `source` VARCHAR(50) DEFAULT 'db',
                    `incident_id` INT NULL,
                    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """))

            # Tabla detection
            await conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS `{table_detection}` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `detected_at` DATETIME NOT NULL,
                    `product_id` INT NULL,
                    `area_id` INT NULL,
                    `shift_id` INT NULL,
                    `status` VARCHAR(50) NULL,
                    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """))

    TenantSession = sessionmaker(tenant_engine, class_=AsyncSession, expire_on_commit=False)
    async with TenantSession() as session:
        for line in lines:
            from sqlalchemy import select
            res = await session.execute(select(ProductionLine).where(ProductionLine.line_code == line))
            if not res.scalar_one_or_none():
                pline = ProductionLine(
                    line_name=line,
                    line_code=line,
                    downtime_threshold=5,
                    is_active=True
                )
                session.add(pline)
        await session.commit()
    
    await tenant_engine.dispose()

    print("\n[OK] Base de datos inicializada correctamente.")

if __name__ == "__main__":
    asyncio.run(init_db())