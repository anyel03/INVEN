# TODO - Dinámica de stock por ruta (ADMIN)

- [ ] Crear endpoint JSON en `apps/ventas/views.py` para obtener `stock_por_producto` dado `ruta_id` (solo ADMIN)
- [ ] Agregar ruta URL para el endpoint en `apps/ventas/urls.py`
- [x] Actualizar `apps/ventas/templates/ventas/form_cliente_venta.html`:
  - [x] Quitar el `location.href=...` del select admin
  - [x] Implementar `fetch()` al endpoint JSON al cambiar ruta
  - [x] Actualizar en la tabla: badge de stock, `max` del input de cantidad
  - [x] Recalcular totales
- [x] Actualizar `apps/ventas/templates/ventas/form.html` con la misma lógica

- [ ] Probar en ejecución:
  - [ ] Entrar como ADMIN
  - [ ] Cambiar ruta y verificar que el stock cambia sin recargar
  - [ ] Verificar que el `max` del input se actualiza
  - [ ] Verificar que ventas siguen validando stock en backend


