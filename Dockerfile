#=============================================================================
# Build environment
FROM --platform=linux/amd64 python:3.10.6-slim as build

# Install Poetry
RUN pip install --upgrade pip && pip install poetry==1.1.14
RUN mkdir /code
WORKDIR /code
# Create Poetry environment
COPY poetry.lock pyproject.toml /code/
RUN POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=true \
    poetry install

# =============================================================================
# Runtime environment
FROM --platform=linux/amd64 python:3.10.6-slim as runtime

# Copy Poetry environment
COPY --from=build /code/.venv /code/.venv

# Update PATH
ENV PATH="/code/.venv/bin:$PATH"
COPY . /code
WORKDIR /code

CMD ["streamlit","run","main.py"]