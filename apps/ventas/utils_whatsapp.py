import os
import re
import urllib.parse
import logging
import requests

logger = logging.getLogger(__name__)

def formatear_telefono_whatsapp(telefono, country_code='593'):
    """Limpia y da formato internacional al número telefónico."""
    if not telefono:
        return None
    # Eliminar cualquier caracter no numérico
    clean = re.sub(r'\D', '', str(telefono))
    if not clean:
        return None
    
    # Si comienza con 0 (ej. 0991234567), reemplazar el 0 inicial por el código de país
    if clean.startswith('0'):
        clean = country_code + clean[1:]
    elif len(clean) == 9: # ej. 991234567
        clean = country_code + clean
        
    return clean


def generar_mensaje_venta(venta):
    """Genera la plantilla de mensaje de WhatsApp para confirmación de venta."""
    cliente_nombre = venta.cliente.nombre if venta.cliente else "Cliente"
    
    items = []
    for det in venta.detalleventa_set.all():
        items.append(f"• {det.cantidad}x {det.producto.nombre} (${det.subtotal:.2f})")
    items_str = "\n".join(items) if items else "• Productos varios"
    
    tipo_str = "Crédito" if venta.tipo == 'CREDITO' else "Contado"
    cobro_str = f"\n📅 *Próximo Cobro:* {venta.proximo_cobro.strftime('%d/%m/%Y')}" if (venta.tipo == 'CREDITO' and venta.proximo_cobro) else ""
    saldo_str = f"\n💳 *Saldo Pendiente:* ${venta.saldo:.2f}" if venta.tipo == 'CREDITO' else ""

    return (
        f"¡Hola *{cliente_nombre}*! 👋\n\n"
        f"Confirmamos el registro de tu compra en *SistemaInVen*:\n"
        f"🧾 *Comprobante de Venta #{venta.id}*\n\n"
        f"*Detalle de Productos:*\n{items_str}\n\n"
        f"💰 *Total Venta:* ${venta.total:.2f}\n"
        f"📌 *Tipo:* {tipo_str}{saldo_str}{cobro_str}\n\n"
        f"¡Muchas gracias por tu compra! 😊"
    )


def generar_mensaje_cobro(cobro):
    """Genera la plantilla de mensaje de WhatsApp para confirmación de cobro."""
    venta = cobro.venta
    cliente_nombre = venta.cliente.nombre if (venta and venta.cliente) else "Cliente"
    
    return (
        f"¡Hola *{cliente_nombre}*! 👋\n\n"
        f"Hemos recibido exitosamente tu pago:\n"
        f"💵 *Recibo de Pago #{cobro.id}*\n"
        f"🔹 *Monto Abonado:* ${cobro.monto:.2f}\n"
        f"🔹 *Método:* {cobro.metodo}\n"
        f"📊 *Saldo Restante (Venta #{venta.id}):* ${venta.saldo:.2f}\n\n"
        f"¡Muchas gracias por tu pago puntual! 👍"
    )


def generar_url_whatsapp(telefono, mensaje):
    """Genera la URL wa.me para autodisparo o enlace en navegador."""
    phone_clean = formatear_telefono_whatsapp(telefono)
    if not phone_clean:
        return None
    encoded_text = urllib.parse.quote(mensaje)
    return f"https://api.whatsapp.com/send?phone={phone_clean}&text={encoded_text}"


def enviar_whatsapp_servidor(telefono, mensaje):
    """
    Envía el mensaje directamente en segundo plano a través de una API de WhatsApp.
    Si existen credenciales en .env (WHATSAPP_API_URL y WHATSAPP_API_TOKEN), realiza la petición HTTP.
    Retorna True si se envió correctamente, False en caso contrario.
    """
    phone_clean = formatear_telefono_whatsapp(telefono)
    if not phone_clean:
        return False
        
    api_url = os.getenv('WHATSAPP_API_URL')
    api_token = os.getenv('WHATSAPP_API_TOKEN')

    if not api_url or not api_token:
        # No hay credenciales de API externa configuradas
        return False

    try:
        # Soporte para proveedores estándar de Gateway (UltraMsg, Wappi, etc.)
        payload = {
            'token': api_token,
            'to': phone_clean,
            'body': mensaje
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        response = requests.post(api_url, data=payload, headers=headers, timeout=5)
        if response.status_code in (200, 201):
            logger.info(f"Mensaje WhatsApp enviado automáticamente a {phone_clean}")
            return True
        else:
            logger.warning(f"Respuesta inesperada de API WhatsApp: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error al enviar mensaje automático por API de WhatsApp: {e}")
        return False
