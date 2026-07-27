docker build --provenance=false -f Dockerfile.lambda -t newsrag-lambda .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker tag newsrag-lambda:latest 814808959551.dkr.ecr.ap-southeast-2.amazonaws.com/newsrag-lambda:latest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker push 814808959551.dkr.ecr.ap-southeast-2.amazonaws.com/newsrag-lambda:latest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Wait a few seconds for ECR to propagate before updating lambda
Start-Sleep -Seconds 5

aws lambda update-function-code --function-name newsrag-etl --image-uri 814808959551.dkr.ecr.ap-southeast-2.amazonaws.com/newsrag-lambda:latest --region ap-southeast-2 --profile default | Out-Null
aws lambda update-function-code --function-name newsrag-rag-api --image-uri 814808959551.dkr.ecr.ap-southeast-2.amazonaws.com/newsrag-lambda:latest --region ap-southeast-2 --profile default | Out-Null

Write-Host "Deployment completed successfully."
