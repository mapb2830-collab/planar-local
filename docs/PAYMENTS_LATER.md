# Activar pagos después — requiere autorización del propietario

Esta versión no incluye SDK, claves, checkout ni webhook Wompi. No existe un interruptor
que convierta una simulación en un pago real: `PAYMENTS_MODE=live` detiene el arranque.

Cuando el propietario autorice la etapa de pagos:

1. Confirmar cuenta comercial Wompi, términos, planes y precios en COP, impuestos,
   política de devoluciones, privacidad y límites reales de cada plan.
2. Implementar primero Wompi Sandbox en un entorno y base separados. Mantener las claves
   privadas e integridad/eventos solo en variables secretas del backend. Nunca en `VITE_*`.
3. Crear órdenes en servidor con usuario, moneda, importe calculado desde catálogo y
   referencia única. Validar el resultado con la API/webhook de Wompi y firma vigente;
   no acreditar por redirección del navegador, screenshot o un estado enviado por el cliente.
4. Añadir transacciones reales en tablas separadas de simulaciones. Índices únicos por
   transacción/evento, idempotencia, conciliación, reversos y reembolsos auditados.
5. Acreditar `paid_credits` solo tras confirmación verificable; implementar consumo atómico,
   cuotas de cada plan y cancelación real. Los créditos `trial` nunca se migran ni convierten.
6. Probar dobles webhooks, firma falsa, cambios de importe/moneda, pagos pendientes,
   concurrencia, chargebacks y reembolsos. Ejecutar pruebas públicas en sandbox.
7. Revisar con el propietario la implementación concreta y el presupuesto de proveedores.
   Solo entonces introducir las claves productivas y habilitar botones de pago.

Revisar la documentación oficial actual antes de implementar: https://docs.wompi.co/
