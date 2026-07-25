const fs = require('fs');
const path = require('path');
const { BedrockRuntimeClient, InvokeModelCommand } = require('@aws-sdk/client-bedrock-runtime');

async function test() {
  const envPath = path.join(process.cwd(), '../.env');
  const envContent = fs.readFileSync(envPath, 'utf8');
  const matchAccess = envContent.match(/^2_ACCESS_KEY_ID=(.*)$/m);
  const matchSecret = envContent.match(/^2_SECRET_ACCESS_KEY=(.*)$/m);
  const matchRegion = envContent.match(/^2_REGION=(.*)$/m);
  
  const client = new BedrockRuntimeClient({
    region: matchRegion[1].trim(),
    credentials: {
      accessKeyId: matchAccess[1].trim(),
      secretAccessKey: matchSecret[1].trim()
    }
  });

  try {
    const command = new InvokeModelCommand({
      modelId: 'amazon.titan-embed-text-v2:0',
      contentType: 'application/json',
      accept: 'application/json',
      body: JSON.stringify({ inputText: 'test', dimensions: 1024, normalize: true })
    });
    const res = await client.send(command);
    console.log("Success");
  } catch (err) {
    console.error("AWS Error:", err);
  }
}
test();
