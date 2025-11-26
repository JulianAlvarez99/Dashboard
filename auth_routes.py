from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from auth_manager import AuthManager
from forms import LoginForm
import security_logger 

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        
        ip_addr = security_logger.get_user_ip(request)
        user_agent = security_logger.get_user_agent(request)
        
        # 1. Verificar Usuario y Contraseña
        user = AuthManager.verify_user(username, password)
        
        if user:
            # 2. Validar Reglas de Negocio (Empresa y Rol)
            # Regla: Rol (admin/cliente) Y Empresa (Camet/CentralNorte)
            valid_roles = ['administrador', 'cliente']
            valid_businesses = ['Camet', 'CentralNorte'] # Agrega aquí otras si es necesario
            
            if user.privilege in valid_roles and user.name_business in valid_businesses:
                # --- LOGIN EXITOSO ---
                login_user(user)
                
                security_logger.log_login_attempt(username, True, ip_addr, user_agent)
                
                # Mensaje de éxito para el usuario
                flash(f'¡Bienvenido {user.username}! Inicio de sesión exitoso.', 'success')
                
                next_page = request.args.get('next')
                if not next_page or not next_page.startswith('/'):
                    next_page = url_for('index')
                    
                return redirect(next_page)
            else:
                # --- USUARIO VÁLIDO PERO SIN PERMISOS DE NEGOCIO ---
                security_logger.log_login_attempt(
                    username, False, ip_addr, user_agent, 
                    failure_reason=f"Acceso denegado por política: {user.name_business}/{user.privilege}"
                )
                flash('Tu usuario no tiene permisos para acceder a este Dashboard.', 'warning')
        else:
            # --- CREDENCIALES INVÁLIDAS ---
            security_logger.log_login_attempt(username, False, ip_addr, user_agent, failure_reason="Credenciales inválidas")
            flash('Usuario o contraseña incorrectos.', 'danger')
    
    return render_template('login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('auth.login'))