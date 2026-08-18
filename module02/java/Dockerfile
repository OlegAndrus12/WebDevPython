##1 which base image to use
# jre, not jdk — nothing is compiled here, the .jar is already built.
#
# Was `openjdk:11-jre-slim`. That image is gone: the openjdk Docker Hub library
# is deprecated and its tags were withdrawn, so the build died with
# "docker.io/library/openjdk:11-jre-slim: not found". eclipse-temurin is the
# replacement the openjdk maintainers point at, and it publishes arm64 too.
FROM eclipse-temurin:11-jre

## set the working directory
WORKDIR /app

## copy project files
COPY . .

# RUN THE BINARY
CMD ["java", "-cp", "JavaApp.jar", "JavaApp"]