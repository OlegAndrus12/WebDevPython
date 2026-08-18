# welcome-to-docker — Part 0, run someone else's image

**This directory is intentionally empty.** There is nothing to build here; that is the
lesson. Before writing a single `Dockerfile`, run an image somebody else already built —
the shortest possible proof that the daemon works, and an introduction to four flags you
will use all module.

The walkthrough is **Part 0** of [../README.md](../README.md).

## Run it

```bash
docker run -d -p 8088:80 --name welcome docker/welcome-to-docker
```

Open <http://localhost:8088>.

| Flag | Meaning |
| --- | --- |
| *(no build)* | `docker/welcome-to-docker` is not on your machine, so Docker pulls it from Docker Hub first |
| `-d` | detached — run in the background and return the prompt, instead of taking over the terminal |
| `-p 8088:80` | publish **host** port 8088 to **container** port 80. The container serves on 80; you reach it on 8088 |
| `--name welcome` | a stable name, so later commands say `welcome` instead of a random hash like `nifty_bardeen` |

Nothing was built, no `Dockerfile` was involved, and the web server inside is nginx — which
you never installed. That is the point: **an image is a shippable, pre-built filesystem plus
a default command.**

## Poke at it

```bash
docker ps                     # running containers, their ports and names
docker logs welcome           # stdout/stderr of the process inside
docker exec -it welcome sh    # a shell inside the running container
    ls /usr/share/nginx/html
    exit
```

## Try the port swap

```bash
docker rm -f welcome
docker run -d -p 9000:80 --name welcome docker/welcome-to-docker
```

Same container, now on <http://localhost:9000>. The right-hand number is fixed by the
software inside the image; the left-hand one is yours to choose. Keeping that distinction
straight is most of what [../flask-node/](../flask-node/) is about.

## Cleanup

A detached container keeps running until you stop it:

```bash
docker stop welcome           # SIGTERM to the main process
docker rm welcome             # delete the stopped container
# or both at once:
docker rm -f welcome

docker rmi docker/welcome-to-docker   # drop the pulled image too
```
