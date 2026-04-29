# Interagent — Red de redes de agentes

## La idea

Internet es una red de redes. Interagent es una red de redes de agentes.

Cada hogar o empresa corre su propio **nodo**: un conjunto de agentes de IA locales
(domótica, clima, agenda, inversiones) que procesan todo sin salir de la red local.
La plataforma Interagent permite que esos nodos aislados **publiquen servicios** para
la comunidad y **consuman servicios de otros**, formando un ecosistema distribuido.

## Analogía con internet

| Internet | Interagent |
|---|---|
| Autonomous System (AS) | Nodo (hogar / empresa) |
| BGP / DNS | Registry central |
| Endpoint HTTP | Servicio de agente |
| CDN / gateway | Interagent Gateway |
| App Store | Marketplace de servicios |

## Componentes

### Nodo (local)
- Orquestador FastAPI + agentes especializados
- Agent SDK: publica y consume servicios de la registry
- Keypair único: firma todas las llamadas salientes
- Metering agent: contabiliza uso para billing

### Registry (cloud)
- Catálogo de servicios con búsqueda, tags, versiones y schemas
- Auth via firma de keypair por nodo
- Metering y billing mensual (cobra al consumidor, paga al proveedor)
- Gateway para llamadas pagas (metering confiable)
- Llamadas free: directo nodo-a-nodo con rate limiting en el SDK

### Community layer
- Stars (1-5) por nodo consumidor post-uso
- Joins: nodos que integraron el servicio
- Maturity score: `stars × log(joins) × log(calls_total)`
- Sistema de reportes + auto-ban preventivo + moderación manual

## Flujo de una llamada

```
Nodo B quiere el servicio "weather.forecast.v1" del Nodo A

Nodo B → [firma request] → Gateway → [valida + mide] → Nodo A → respuesta
                                                               ↓
                                                      Gateway → Nodo B
```

Free tier: Nodo B → [firma request] → Nodo A directamente (sin gateway)

## Modelo de negocio

| Tier | Precio/mes | Llamadas/mes |
|------|-----------|-------------|
| Free | $0 | 1.000 por servicio |
| Starter | $9 | 50.000 totales |
| Pro | $49 | 500.000 totales |
| Enterprise | custom | ilimitadas |

Split por llamada paga: **70% proveedor / 25% plataforma / 5% comunidad**

Cash out mensual a proveedores vía Stripe Connect.

## Relación con home-agents

El proyecto home-agents (`~/workspace/home-agents`) es el nodo de referencia:
- La FASE 3 (orquestador FastAPI) se convierte en la base del SDK
- El agente de clima publica `weather.forecast.v1` como primer servicio real
- Sirve como caso de estudio para la documentación de onboarding

## Preguntas abiertas clave

1. **NAT traversal**: ¿cómo exponer un nodo doméstico a internet?
   Candidatos: Cloudflare Tunnel (gratis, confiable), relay server en registry.

2. **Registry centralizada vs federada**: MVP centralizado, protocolo diseñado
   para ser federable en el futuro.

3. **Subdominios por nodo**: `node-abc123.interagent.io` requiere wildcard SSL
   pero da mejor UX que IPs directas.

## Estructura del repositorio

```
interagent/
├── CONCEPT.md              ← este archivo
├── protocol/
│   ├── service.schema.yaml     definición formal de un servicio
│   └── registry.openapi.yaml  API de la registry
├── sdk/
│   └── README.md           diseño del SDK
└── monetization/
    └── model.md            modelo de negocio detallado
```
