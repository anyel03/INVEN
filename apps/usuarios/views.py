
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
import hashlib
from .models import Usuario


def login_view(request):
    """
    Vista de login - Autenticación custom con hash SHA256
    """
    if request.session.get('user_id'):
        return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        # Validacion de campos vacíos
        if not email or not password:
            messages.error(request, 'Por favor ingresa email y contraseña')
            return render(request, 'login.html')

        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        try:
            # Buscar usuario activo
            usuario = Usuario.objects.get(
                email=email,
                password=hashed_password,
                activo=True
            )

            request.session['user_id'] = usuario.id
            request.session['user_name'] = usuario.nombre
            request.session['user_email'] = usuario.email
            request.session['rol_id'] = usuario.rol.id
            request.session['rol_nombre'] = usuario.rol.nombre

            messages.success(request, f'¡Bienvenido {usuario.nombre}!')
            return redirect('dashboard')

        except Usuario.DoesNotExist:
            messages.error(request, 'Email o contraseña incorrectos')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    return render(request, 'login.html')


def logout_view(request):
    """
    Cerrar sesión - Limpiar session
    """
    user_name = request.session.get('user_name', 'Usuario')
    request.session.flush()
    messages.success(request, f'Sesión cerrada. ¡Hasta luego {user_name}!')
    return redirect('login')


def dashboard_view(request):
    """
    Dashboard principal - Requiere login
    """
    if not request.session.get('user_id'):
        return redirect('login')

    context = {
        'user': request.session.get('user_name'),
        'rol': request.session.get('rol_nombre'),
    }
    return render(request, 'dashboard.html', context)


def api_check_session(request):
    """
    API para verificar sesión (AJAX)
    """
    user_id = request.session.get('user_id')
    if user_id:
        return JsonResponse({
            'logged_in': True,
            'user_name': request.session.get('user_name'),
            'rol': request.session.get('rol_nombre')
        })
    return JsonResponse({'logged_in': False})
