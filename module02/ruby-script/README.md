# ruby-script — your turn

[script.rb](script.rb) prints a random inspirational quote inside an ASCII box. It needs
nothing but a Ruby interpreter.

[Dockerfile](Dockerfile) is here too — **it is the reference solution, not the lesson.**
Write your own first, then compare. It is line for line the same shape as
[../python-script/Dockerfile](../python-script/Dockerfile); only the base image and the
interpreter changed. That is the whole promise of Docker: the interface to a Ruby app and
a Python app is the same two commands.

The walkthrough is **Part 1.2** of [../README.md](../README.md). This is the short version.

## Step 1 — prove it works without building anything

Mount the source into an off-the-shelf image. Nothing is built, nothing is left behind:

```bash
cd module02/ruby-script

docker run --rm -v "$PWD":/app -w /app ruby:3.3-slim ruby script.rb
```

- `-v "$PWD":/app` — bind-mounts the host directory into the container.
- `-w /app` — sets the working directory inside the container.
- `--rm` — delete the container once the script exits.

This is the fastest way to run *anything* in a throwaway environment. It is also the wrong
way to ship software: the code lives outside the image, so nothing is reproducible.

## Step 2 — write the Dockerfile, then build

Write it from memory before opening [Dockerfile](Dockerfile):

```dockerfile
FROM ruby:3.3-slim
WORKDIR /app
COPY script.rb script.rb
CMD ["ruby", "script.rb"]
```

```bash
docker build -t ruby-script .
docker run --rm ruby-script
```

Run it a few times — the quote is picked at random, so the same image gives different
output. The image is fixed; the container's process is not.

## Things worth trying

```bash
docker run --rm ruby-script ruby -v      # override CMD
docker run --rm -it ruby-script bash     # look around inside
docker history ruby-script               # one layer per instruction
```

## Cleanup

```bash
docker rmi ruby-script
```
