# Métodos de pago para tiendas en línea

## Tarjetas de crédito y débito
Puedes integrar pasarelas que aceptan Visa, Mastercard, American Express. Opciones habituales: **Stripe**, **PayPal**, **Mercado Pago**, **Open Pay**. En Tiendanube/Nuvemshop muchas vienen ya disponibles en la configuración de la tienda.

## Stripe
Stripe permite cobrar con tarjeta, Apple Pay, Google Pay y en algunos países transferencias. Se configura desde el panel de la tienda añadiendo la app o integración de Stripe e ingresando las claves API (publishable key y secret key). Las comisiones suelen ser un porcentaje por transacción más un fijo.

## PayPal
PayPal está muy extendido y da confianza al comprador. El comprador puede pagar con su cuenta PayPal o con tarjeta a través de PayPal. Se integra mediante botón de pago o checkout express. Comisiones por venta según el plan.

## Mercado Pago
Ideal para México, Argentina, Colombia, Brasil y otros países de Latinoamérica. Acepta tarjetas, efectivo en puntos de pago, transferencia y dinero en cuenta de Mercado Pago. La integración se hace desde el panel de la tienda eligiendo Mercado Pago como método de pago y vinculando la cuenta.

## Pagos en efectivo y transferencia
Muchas tiendas ofrecen pago en OXXO, SPEI, transferencia bancaria o depósito. Esto se configura como “método de pago manual”: el cliente elige la opción y la tienda confirma el pago cuando recibe el dinero. Útil para evitar comisiones de pasarela en ventas locales.

## Recomendación
Para empezar suele bastar con un solo método (por ejemplo Mercado Pago en LATAM o Stripe/PayPal a nivel internacional). Luego se pueden añadir más según el público y el país.
