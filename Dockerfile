FROM public.ecr.aws/lambda/python:3.11

# Copy requirements.txt first for better caching
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all necessary files
COPY lambda_function.py ${LAMBDA_TASK_ROOT}
COPY functions.py ${LAMBDA_TASK_ROOT}
COPY constants.py ${LAMBDA_TASK_ROOT}
COPY ability_ids.json ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler
CMD [ "lambda_function.handler" ]