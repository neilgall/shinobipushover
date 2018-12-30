FROM frolvlad/alpine-python3

ENV SHINOBI_BASE_URL "http://example.com/"
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

EXPOSE 8000

ENTRYPOINT ["gunicorn", "--bind", "127.0.0.1:8000", "shinobipushover"]
