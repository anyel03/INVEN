from django import template

register = template.Library()


@register.filter(name="get_item")
def get_item(value, key):
    """Devuelve value[key] si existe; si no, retorna None.

    Uso en templates:
        {% load ventas_extras %}
        {{ mi_dict|get_item:algun_id|default:0 }}
    """
    try:
        return value.get(key)
    except Exception:
        try:
            return value[key]
        except Exception:
            return None

