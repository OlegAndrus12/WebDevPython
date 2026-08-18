# java — an image over a pre-built artifact

This directory holds a compiled [JavaApp.jar](JavaApp.jar) and a [Dockerfile](Dockerfile),
and nothing else. There is no source, no `pom.xml`, no build tool — the image only has to
supply a JRE and a command line.

That makes it the counter-example to
[../microservices/order-management/](../microservices/order-management/), where a full
Maven image compiles *inside* the container and the JDK ships to production along with the
app. Same language, opposite choice.

The walkthrough is **Part 1.3** of [../README.md](../README.md). This is the short version.

## Run it

```bash
cd module02/java

docker build -t java-app .
docker run --rm java-app
```

## The whole Dockerfile

```dockerfile
FROM eclipse-temurin:11-jre   # jre, not jdk — we don't compile here
WORKDIR /app
COPY . .                      # copies JavaApp.jar (and the Dockerfile, see below)
CMD ["java", "-cp", "JavaApp.jar", "JavaApp"]
```

## Two lessons hiding in here

**1. `COPY . .` copies too much.** The Dockerfile itself lands inside the image. Check:

```bash
docker run --rm java-app ls -la /app
```

That is why the microservices examples all carry a `.dockerignore`, which works like
`.gitignore` but for the build context — matched files are never even sent to the daemon:

```
Dockerfile
README.md
```

[../microservices/order-management/.dockerignore](../microservices/order-management/.dockerignore)
is the serious version: it excludes `target/`, `.git/` and the Maven wrapper, which would
otherwise be uploaded on every single build.

**2. Runtime image ≠ build image.** Here the `.jar` was built on the host, so the image
carries a JRE and 3 KB of application. Multi-stage builds (compile in one image, copy just
the artifact into a slim one) are how you get both without choosing. Compare sizes:

```bash
docker images --format "table {{.Repository}}\t{{.Size}}"
```

## Cleanup

```bash
docker rmi java-app
```

Next: [../flask-node/](../flask-node/) — where one container stops being enough.
