# Modelo de monetización — Interagent Platform

## Premisa

Interagent es un marketplace bilateral:
- **Proveedores**: nodos que publican servicios y cobran por su uso
- **Consumidores**: nodos que integran servicios de otros y pagan por el uso
- **Un mismo nodo puede ser los dos al mismo tiempo**

La plataforma toma un porcentaje de cada transacción como intermediario,
igual que App Store (30%) o Stripe (2.9% + fijo).

---

## Tiers de plan para consumidores

| Tier | Precio/mes | Llamadas/mes | SLA | Soporte |
|------|-----------|-------------|-----|---------|
| **Free** | $0 | 1.000 por servicio free | Sin SLA | Community |
| **Starter** | $9 | 50.000 totales | 99% uptime | Email |
| **Pro** | $49 | 500.000 totales | 99.9% uptime | Priority |
| **Enterprise** | custom | Ilimitadas | custom SLA | Dedicado |

- Overage (por encima del límite): $0.002 por llamada adicional (Starter/Pro)
- El plan free solo da acceso a servicios free tier

---

## Tiers de publicación para proveedores

| Tier del servicio | ¿Quién puede publicarlo? | Monetización |
|---|---|---|
| **free** | Cualquier nodo | Sin ingresos para el proveedor |
| **starter** | Nodos con plan Starter o superior | El consumidor paga, proveedor recibe 70% |
| **pro** | Nodos con plan Pro o superior | Ídem |
| **enterprise** | Nodos Enterprise | Precio y split custom |

Un nodo free puede publicar servicios, pero solo en tier free (sin cobro).
Para cobrar por sus servicios, el nodo proveedor debe tener al menos plan Starter.

---

## Split de revenue por llamada paga

```
Precio por 1.000 llamadas: $X (definido por el proveedor)

  70%  →  Proveedor del servicio
  25%  →  Plataforma Interagent
   5%  →  Fondo de moderación y comunidad
```

El fondo de comunidad se usa para:
- Financiar moderación manual de reportes
- Grants para servicios open source destacados
- Infraestructura del relay server (NAT traversal)

---

## Cash in y cash out

### Cash in (plataforma recibe)
- Suscripciones mensuales de nodos (Starter, Pro, Enterprise)
- 25% de cada llamada paga entre nodos
- Overages de llamadas

### Cash out (plataforma paga)
- 70% de cada llamada paga → al nodo proveedor (mensual)
- Método: Stripe Connect (ACH / SEPA / transferencia local según país)
- Umbral mínimo de pago: $10 acumulados (para reducir costos de transferencia)
- Frecuencia: primer día hábil de cada mes, por el mes anterior

---

## Ejemplo numérico

Nodo A publica `weather.forecast.v1` a $1 por 1.000 llamadas.

En el mes de mayo recibe 200.000 llamadas pagas de 15 nodos distintos:

```
Revenue bruto:          200.000 / 1.000 × $1    = $200
  → Proveedor (70%):                               $140
  → Plataforma (25%):                               $50
  → Fondo comunidad (5%):                           $10
```

El Nodo A recibe $140 el 1 de junio vía Stripe Connect.
Si el Nodo A tiene plan Starter ($9/mes) para consumir servicios de otros,
su factura neta de junio es $9 - $140 = recibe $131.

---

## Estrategia de crecimiento

### Por qué el free tier es crítico
- Reduce el costo de entrada a cero (adopción masiva)
- Los proveedores publican en free para ganar joins y stars → suben maturity score
- Un servicio con maturity_score alto atrae consumidores pagos → el proveedor sube a tier pago
- Efecto red: más nodos → más servicios → más valor para cada nodo

### Incentivos para publicar servicios de calidad
- **Maturity score** determina el ranking en búsquedas (mejor score = más visibilidad)
- **Badge "Verified Provider"**: nodos con >1.000 llamadas y 0 reportes
- **Descuento en plan propio**: top 10 proveedores del mes reciben 20% off en su siguiente mes
- **Featured services**: la plataforma puede destacar servicios en la home (no pago, por calidad)

### Prevención de fraude
- Rate limiting estricto en free tier (implementado en el SDK del proveedor)
- Metering cross-referenciado: el gateway valida contra los reportes del proveedor
- Anomaly detection: picos de llamadas fuera de patrón → revisión automática
- Chargebacks: si un proveedor reporta datos falsos, se suspende y se retiene el pago

---

## Comparación con modelos similares

| Plataforma | Split proveedor | Modelo |
|---|---|---|
| Apple App Store | 70% | Subscriptions / one-time purchase |
| Google Play | 85% (después de $1M) | Ídem |
| Stripe Connect | ~97% (cobran el 3%) | Pagos directos |
| AWS Marketplace | 75-80% | SaaS / API |
| **Interagent** | **70%** | API calls / subscriptions |

El 70/25/5 es competitivo con App Store y más generoso que AWS Marketplace,
justificado porque Interagent provee la infraestructura (gateway, auth, metering,
NAT traversal) además del marketplace.

---

## Roadmap de monetización

- [ ] Etapa 3 (Free tier): free tier sin cobro ni pago — solo registro y metering
- [ ] Etapa 5a: Stripe Subscriptions — cobrar planes Starter/Pro
- [ ] Etapa 5b: Stripe Connect — pagar a proveedores
- [ ] Etapa 5c: Gateway de llamadas pagas — metering confiable para split
- [ ] Etapa 5d: Dashboard de earnings para proveedores (en tiempo real)
- [ ] Etapa 6: Enterprise — pricing custom, contratos, SLA garantizado
