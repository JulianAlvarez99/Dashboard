from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from auth_manager import AuthManager
from forms import LoginForm
# Importamos tu logger existente
import security_logger 

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Si ya está logueado, mandar al dashboard
    if current_user.is_authenticated:
        return redirect(url_for('index')) # 'index' es la función en app.py

    form = LoginForm()
    
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        
        # Obtener IP y User Agent para el log (usando funciones de tu logger)
        ip_addr = security_logger.get_user_ip(request)
        user_agent = security_logger.get_user_agent(request)
        
        # Verificar credenciales
        user = AuthManager.verify_user(username, password)
        
        if user:
            login_user(user)
            
            # Registrar éxito en tu sistema de logs
            security_logger.log_login_attempt(username, True, ip_addr, user_agent)
            
            # Manejo seguro de redirección "next" (evita Open Redirect Vulnerability)
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('index')
                
            return redirect(next_page)
        else:
            # Registrar fallo
            security_logger.log_login_attempt(username, False, ip_addr, user_agent, failure_reason="Credenciales inválidas")
            flash('Usuario o contraseña incorrectos.', 'danger')
    
    return render_template('login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))