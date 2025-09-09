# Builder
FROM python:3.13-slim AS builder

WORKDIR /app
COPY ./app/requirements.txt .

RUN pip install --no-cache-dir --prefix="/install" -r requirements.txt

# Final Image
FROM python:3.13-slim

RUN adduser --system --group --no-create-home mototwist
RUN mkdir /gpx && chown mototwist:mototwist /gpx

WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=mototwist:mototwist ./app .

USER mototwist

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]