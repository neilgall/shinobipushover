FROM frolvlad/alpine-python3

# Install curl for debugging
RUN apk update
RUN apk add curl

ENV SHINOBI_EXTERNAL_URL "http://example.com/"
ENV SHINOBI_INTERNAL_URL "http://localhost:8000"
ENV SHINOBI_API_KEY "api-key"
ENV SHINOBI_GROUP_KEY "group-key"
ENV SHINOBI_USER_EMAIL "user@example.com"
ENV SHINOBI_USER_PASS "monkey"
ENV PUSHOVER_TOKEN "token"
ENV PUSHOVER_USER "user"

WORKDIR /opt/shinobipushover

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY shinobipushover.py .
RUN /usr/bin/python3 shinobipushover.py initdb

EXPOSE 8000

ENTRYPOINT ["gunicorn", "--bind", "0.0.0.0:8000", "shinobipushover"]
