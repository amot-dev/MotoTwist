# Builder
FROM python:3.13-slim AS builder

WORKDIR /app
COPY ./app/requirements.txt .

RUN pip install --no-cache-dir --prefix="/install" -r requirements.txt

# Final Image
FROM python:3.13-slim

ARG MOTOTWIST_VERSION=dev
ENV MOTOTWIST_VERSION=${MOTOTWIST_VERSION}

RUN adduser --system --group --no-create-home mototwist
RUN mkdir /gpx && chown mototwist:mototwist /gpx

WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=mototwist:mototwist ./app .

USER mototwist

EXPOSE 8000

ENTRYPOINT ["python", "main.py"]