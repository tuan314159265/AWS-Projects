import { NextRequest, NextResponse } from 'next/server';
import { Pool } from 'pg';
import { BedrockRuntimeClient, InvokeModelCommand } from '@aws-sdk/client-bedrock-runtime';

import * as fs from 'fs';
import * as path from 'path';

const pool = new Pool({
  host: process.env.DB_HOST,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  port: parseInt(process.env.DB_PORT || '5432'),
  ssl: { rejectUnauthorized: false }
});

const getBedrockClient = () => {
  // Read .env file manually because Next.js ignores keys starting with numbers
  const envPath = path.join(process.cwd(), '../.env');
  let accessKeyId = process.env['2_ACCESS_KEY_ID'];
  let secretAccessKey = process.env['2_SECRET_ACCESS_KEY'];
  let region = process.env['2_REGION'];
  let modelId = process.env.BEDROCK_EMBEDDING_MODEL_ID;

  if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, 'utf8');
    const matchAccess = envContent.match(/^2_ACCESS_KEY_ID=(.*)$/m);
    const matchSecret = envContent.match(/^2_SECRET_ACCESS_KEY=(.*)$/m);
    const matchRegion = envContent.match(/^2_REGION=(.*)$/m);
    const matchModelId = envContent.match(/^BEDROCK_EMBEDDING_MODEL_ID=(.*)$/m);
    
    if (!accessKeyId && matchAccess) accessKeyId = matchAccess[1].trim();
    if (!secretAccessKey && matchSecret) secretAccessKey = matchSecret[1].trim();
    if (!region && matchRegion) region = matchRegion[1].trim();
    if (matchModelId) modelId = matchModelId[1].trim(); // Override from root .env
  }

  const credentials = accessKeyId ? {
    accessKeyId: accessKeyId,
    secretAccessKey: secretAccessKey || ''
  } : undefined;

  // We attach modelId to the bedrockClient object for later use
  const client = new BedrockRuntimeClient({
    region: region || process.env.BEDROCK_REGION || 'ap-southeast-1',
    credentials
  });
  
  (client as any)._modelId = modelId || 'cohere.embed-multilingual-v3';
  return client;
};

const bedrockClient = getBedrockClient();

async function getEmbedding(text: string): Promise<number[]> {
  try {
    const modelId = (bedrockClient as any)._modelId;
    const input = {
      modelId: modelId,
      contentType: 'application/json',
      accept: 'application/json',
      body: JSON.stringify({
        texts: [text],
        input_type: 'search_query'
      })
    };
    
    const command = new InvokeModelCommand(input);
    const response = await bedrockClient.send(command);
    const responseBody = JSON.parse(new TextDecoder().decode(response.body));
    return responseBody.embeddings[0];
  } catch (error: any) {
    console.error("Error calling Bedrock embedding:", error);
    throw new Error("Bedrock: " + error.message);
  }
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const q = searchParams.get('q');
    const limit = parseInt(searchParams.get('limit') || '10');

    if (!q) {
      return NextResponse.json([]);
    }

    // 1. Get embedding for query
    const embedding = await getEmbedding(q);
    const vectorString = `[${embedding.join(',')}]`;

    // 2. Perform vector search in pgvector
    const query = `
      SELECT 
        a.article_id || '_' || v.chunk_index as id,
        a.title,
        am.url,
        s.domain as source,
        t.date as published_date,
        string_agg(DISTINCT au.author_name, ', ') as author,
        SUBSTRING(c.content, 1, 150) as snippet,
        1 - (v.embedding <=> $1::vector) as similarity
      FROM fact_vectors v
      JOIN fact_chunks c ON v.article_id = c.article_id AND v.chunk_index = c.chunk_index
      JOIN fact_articles a ON v.article_id = a.article_id
      LEFT JOIN article_metadata am ON a.url_hash = am.url_hash
      LEFT JOIN dim_source s ON a.source_id = s.source_id
      LEFT JOIN dim_time t ON a.time_id = t.time_id
      LEFT JOIN fact_article_authors faa ON a.article_id = faa.article_id
      LEFT JOIN dim_author au ON faa.author_id = au.author_id
      GROUP BY a.article_id, v.chunk_index, a.title, am.url, s.domain, t.date, c.content, v.embedding
      ORDER BY similarity DESC
      LIMIT $2
    `;

    const result = await pool.query(query, [vectorString, limit]);
    
    return NextResponse.json(result.rows);
  } catch (error: any) {
    console.error("Semantic search error:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
