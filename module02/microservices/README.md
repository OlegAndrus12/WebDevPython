# microservices — Compose at scale

Seven services in five languages, started with one command. Conceptually there is nothing
here that [../flask-node/](../flask-node/) did not already teach — service names as
hostnames, env vars for configuration, one network. Only the number of moving parts is new.

| Service | Directory | Stack | Container port | Role |
| --- | --- | --- | --- | --- |
| `ecommerce-ui` | [ecommerce-ui/](ecommerce-ui/) | React + Express | 4000 | UI + API gateway |
| `product-catalog` | [product-catalog/](product-catalog/) | Node / Express | 3001 | Product list |
| `product-inventory` | [product-inventory/](product-inventory/) | Python / Flask | 3002 | Stock levels |
| `profile-management` | [profile-management/](profile-management/) | Node + JWT | 3003 | Signup / signin |
| `contact-support-team` | [contact-support-team/](contact-support-team/) | Python / Flask | 8000 | Contact form |
| `shipping-and-handling` | [shipping-and-handling/](shipping-and-handling/) | Go | 8080 | Shipping fees |
| `order-management` | [order-management/](order-management/) | Java / Spring Boot | 9090 | Cart & checkout |

## Run it

```bash
cd module02/microservices

docker compose up --build      # add -d to detach
```

Then open <http://localhost:4000>.

> **The first build takes 5–15 minutes.** `order-management` downloads the entire Maven
> dependency tree and runs `mvn install`; `ecommerce-ui` runs `npm install && npm run build`
> for a Create-React-App client. Subsequent builds hit the layer cache. Watch progress with
> `docker compose logs -f order-management`.

> **Apple Silicon:** `node:14` and `maven:3.6.3-openjdk-17-slim` are amd64-only and run
> under emulation. If a build dies with `no matching manifest`, add
> `platform: linux/amd64` to the service in [docker-compose.yaml](docker-compose.yaml).

## Smoke-test each service

Every service publishes its port, so you can talk to them directly from the host:

```bash
curl -s localhost:3001/api/products | head -c 300      # catalog
curl -s localhost:3002/api/inventory                   # inventory
curl -s "localhost:8080/shipping-fee?product_id=1"     # shipping (Go)
curl -s localhost:8000/api/contact-message             # support
curl -s localhost:9090/api/orders/1/cart               # orders (Spring)

curl -s -X POST localhost:3003/api/signup \
  -H 'Content-Type: application/json' \
  -d '{"firstName":"Ada","lastName":"L","address":"1 St","postalCode":"X","email":"a@b.c","password":"pw"}'
```

## How the calls actually flow

```
browser ──/api/products──► ecommerce-ui:4000 ──http://product-catalog:3001──► product-catalog
                            (Express server)
                                                order-management:9090 ──► product-catalog:3001
                                                                      ──► product-inventory:3002
                                                                      ──► shipping-and-handling:8080
```

The React code fetches **relative** URLs — `fetch('/api/products')` — so the browser only
ever talks to port 4000. The Express server in
[ecommerce-ui/server/routes/products.js](ecommerce-ui/server/routes/products.js) then
forwards to `${REACT_APP_PRODUCT_API_HOST}:3001`, where that variable is
`http://product-catalog`, injected by [docker-compose.yaml](docker-compose.yaml).

It has to be that way, because **the browser runs on your Mac, not on the Docker network.**
`http://product-catalog:3001` is meaningless out there. Only a process *inside* the network
can resolve service names — so the UI container proxies. A pleasant side effect: everything
the browser sees is same-origin, so there is no CORS to configure.

`order-management` is the pure server-to-server case — three outbound calls, three service
names from `environment:`, mapped onto `@Value("${PRODUCT_CATALOG_API_HOST}")` in
`OrderService.java`. Its `application.properties` defaults are `http://localhost`: correct
when a developer runs everything on their laptop, wrong in containers, which is exactly why
compose overrides them.

## Prove that service names only resolve inside the network

```bash
# From your Mac — the name does not exist out here
curl http://product-catalog:3001/api/products
# curl: (6) Could not resolve host: product-catalog

# From inside the network — resolves and answers
docker compose exec ecommerce-ui getent hosts product-catalog
docker compose exec ecommerce-ui \
  node -e "require('http').get('http://product-catalog:3001/api/products', r => console.log('status', r.statusCode))"
```

Reaching the same container through its *published* port from the host
(`curl localhost:3001/api/products`) works fine — two different paths to one container,
which is the whole distinction between publishing and networking.

## Without Compose — the same thing by hand

Worth typing once, to see what `docker compose up` is doing. Seven builds, a network,
seven runs in dependency order, and every env var spelled out:

```bash
for s in product-catalog product-inventory shipping-and-handling \
         profile-management contact-support-team order-management ecommerce-ui; do
  docker build -t $s ./$s
done

docker network create shop-net

docker run -d --name product-catalog       --network shop-net -p 3001:3001 product-catalog
docker run -d --name product-inventory     --network shop-net -p 3002:3002 product-inventory
docker run -d --name profile-management    --network shop-net -p 3003:3003 profile-management
docker run -d --name contact-support-team  --network shop-net -p 8000:8000 contact-support-team
docker run -d --name shipping-and-handling --network shop-net -p 8080:8080 shipping-and-handling

docker run -d --name order-management --network shop-net -p 9090:9090 \
  -e PRODUCT_CATALOG_API_HOST=http://product-catalog \
  -e PRODUCT_INVENTORY_API_HOST=http://product-inventory \
  -e SHIPPING_HANDLING_API_HOST=http://shipping-and-handling \
  order-management

docker run -d --name ecommerce-ui --network shop-net -p 4000:4000 \
  -e REACT_APP_PRODUCT_API_HOST=http://product-catalog \
  -e REACT_APP_INVENTORY_API_HOST=http://product-inventory \
  -e REACT_APP_PROFILE_API_HOST=http://profile-management \
  -e REACT_APP_CONTACT_API_HOST=http://contact-support-team \
  -e REACT_APP_SHIPPING_API_HOST=http://shipping-and-handling \
  -e REACT_APP_ORDER_API_HOST=http://order-management \
  ecommerce-ui
```

Tear it down again:

```bash
docker rm -f product-catalog product-inventory profile-management contact-support-team \
             shipping-and-handling order-management ecommerce-ui
docker network rm shop-net
```

Twenty-odd lines and a strict order, against `docker compose up`. Every name after
`--name` is a hostname the other containers resolve — the same mechanism compose gives
you for free from the service keys.

## Everyday commands

```bash
docker compose ps
docker compose logs -f order-management
docker compose exec product-catalog sh
docker compose up -d --build product-catalog   # rebuild + replace one service only
docker compose restart ecommerce-ui
```

## Cleanup

```bash
docker compose down
docker compose down --rmi local   # also delete the images this project built
```

## Worth noticing

- **Every service publishes a port.** Convenient for the smoke tests above, but only
  `ecommerce-ui:4000` actually needs to be reachable from the host — compare with `mongo`
  in [../flask-node/docker-compose.yaml](../flask-node/docker-compose.yaml), which
  publishes nothing. Removing the other six `ports:` blocks and checking the app still
  works is a good exercise.
- **Every directory carries a `.dockerignore`.** Without them, `node_modules/` and
  `target/` would be uploaded to the daemon on every build.
- **`depends_on` orders starts, not readiness.** `ecommerce-ui` may come up before
  `order-management` has finished booting Spring; the UI just errors until it does.
