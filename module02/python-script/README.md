# python-script — the minimal Dockerfile

The smallest useful example in the module: one Python file that prints an ASCII banner,
and the four-instruction [Dockerfile](Dockerfile) that turns it into a shippable image.

Nothing is installed, nothing is networked, nothing persists. The only idea here is the
`build` → `run` cycle.

| File | What it is |
| --- | --- |
| [main.py](main.py) | Prints a "Python!" ASCII banner and exits |
| [Dockerfile](Dockerfile) | `FROM` / `WORKDIR` / `COPY` / `CMD` — the four instructions almost every image starts with |

The walkthrough is **Part 1.1** of [../README.md](../README.md). This is the short version.

## Run it

```bash
cd module02/python-script

# 1. Build an image and tag it. The trailing "." is the BUILD CONTEXT —
#    the directory sent to the daemon, and the root for every COPY path.
docker build -t python-script .

# 2. Confirm it exists
docker images python-script

# 3. Run a container from it. --rm deletes the container after it exits.
docker run --rm python-script
```

Expected output: the ASCII banner, then the container exits — **a container lives exactly
as long as its main process.** There is no server here, so there is nothing to keep it up
and nothing to publish with `-p`.

## The whole Dockerfile

```dockerfile
FROM python:3.14.0rc1-slim   # 1. base image = OS + runtime, already built for you
WORKDIR /app                 # 2. cd inside the image; created if missing
COPY main.py main.py         # 3. host file → image layer
CMD ["python", "main.py"]    # 4. default command when a container starts
```

## Things worth trying

```bash
# Override CMD at runtime — the image is a filesystem, not a fixed program
docker run --rm python-script python -c "import sys; print(sys.version)"

# Get a shell inside to look around
docker run --rm -it python-script bash
ls -l /app && pwd && exit

# See the layers the build produced, one per instruction
docker history python-script
```

## Build vs. run

| | `docker build` | `docker run` |
| --- | --- | --- |
| Produces | An **image** (read-only, layered) | A **container** (image + writable layer + process) |
| Runs | `RUN` instructions | `CMD` / `ENTRYPOINT` |
| Frequency | Once per code change | Any number of times per image |

## Cleanup

```bash
docker rmi python-script
```
