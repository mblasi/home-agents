# Interagent SDK

Biblioteca Python para que un nodo publique y consuma servicios de la registry Interagent.

## Instalación (futura)

```bash
pip install interagent-sdk
```

## CLI

```bash
# Registrar este nodo en la registry (genera keypair local)
interagent init

# Publicar un servicio (lee interagent/protocol/service.schema.yaml)
interagent publish ./my-service.schema.yaml

# Listar servicios disponibles
interagent list [--category environment] [--tier free] [--sort maturity_score]

# Llamar un servicio remoto
interagent call weather.forecast.v1 --input '{"location": "-34.6,-58.4", "days": 3}'

# Ver uso y earnings del mes actual
interagent usage
```

## Python API

### Publicar un servicio

```python
from interagent import Node, Service

node = Node.from_config("~/.interagent/node.yaml")  # keypair + node_id

service = Service.from_schema("./weather.schema.yaml")
node.publish(service)
```

### Exponer un agente como servicio

```python
from interagent import Node, expose
from fastapi import FastAPI

app = FastAPI()
node = Node.from_config("~/.interagent/node.yaml")

@expose(node, service_id="weather.forecast.v1")
async def weather_handler(location: str, days: int = 1):
    # lógica del agente local
    return {"temperature_c": 22.5, "forecast": [...]}

# El decorador registra el endpoint y lo firma automáticamente.
# Rate limiting del free tier se aplica aquí.
```

### Consumir un servicio remoto

```python
from interagent import Node

node = Node.from_config("~/.interagent/node.yaml")
client = node.client()

result = await client.call(
    "weather.forecast.v1",
    input={"location": "-34.6,-58.4", "days": 3}
)
print(result["current"]["temperature_c"])
```

### Integrar con el orquestador existente (home-agents)

```python
# En ha-bridge/orchestrator.py — cuando no hay agente local para resolver
# la intención, delegar a la registry:

from interagent import Node

node = Node.from_config("~/.interagent/node.yaml")
client = node.client()

async def resolve_intent(intent: str, params: dict):
    # 1. Intentar con agente local
    if intent in local_agents:
        return await local_agents[intent].handle(params)
    
    # 2. Buscar en registry
    services = await client.search(query=intent, tier="free")
    if services:
        return await client.call(services[0].id, input=params)
    
    return None
```

## Firma de requests

Cada llamada saliente incluye:

```
X-Node-Id: node-abc123
X-Timestamp: 1745800000000
X-Node-Signature: base64(Ed25519.sign(SHA256(body_bytes + timestamp_bytes)))
```

El SDK firma automáticamente. La clave privada nunca sale del nodo.

## Configuración local

```yaml
# ~/.interagent/node.yaml
node_id: "node-abc123"
private_key: "ed25519:..."         # generada en `interagent init`, nunca sube a la registry
public_key: "ed25519:..."
registry_url: "https://registry.interagent.io/v1"
plan: free
```

## Problema de NAT traversal

Un nodo doméstico típicamente está detrás de NAT y no tiene IP pública.
Para recibir llamadas entrantes, el SDK soportará (en orden de preferencia):

1. **Cloudflare Tunnel** (recomendado): `cloudflared tunnel` expone el puerto local
   sin abrir el router. Gratis, confiable, sin IP pública.
2. **Relay server**: la registry actúa de relay, el nodo mantiene una conexión
   WebSocket persistente y el gateway inyecta las llamadas por esa conexión.
3. **IP pública / VPN**: para nodos con IP fija o conectados a una VPN.

El SDK detecta el método disponible y lo configura automáticamente en `interagent init`.

## Roadmap del SDK

- [ ] `interagent init` — registro de nodo + generación de keypair
- [ ] `interagent publish` — publicar/actualizar servicio en registry
- [ ] `interagent list` / `interagent search` — descubrimiento
- [ ] `interagent call` — llamada CLI a servicio remoto
- [ ] `Node` + `Service` + client Python API
- [ ] Decorador `@expose` para FastAPI
- [ ] Rate limiting automático (free tier)
- [ ] Metering reporting (reportar llamadas recibidas)
- [ ] NAT traversal: Cloudflare Tunnel automático
- [ ] NAT traversal: relay WebSocket como fallback
- [ ] `interagent usage` — dashboard de consumo y earnings en terminal
