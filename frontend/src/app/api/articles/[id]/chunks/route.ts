import { NextRequest, NextResponse } from 'next/server';
import { Pool } from 'pg';

const pool = new Pool({
  host: process.env.DB_HOST,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  port: parseInt(process.env.DB_PORT || '5432'),
  ssl: { rejectUnauthorized: false }
});

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = await params;
    const articleId = id;

    // Join fact_vectors with dim_content to get the actual text
    const query = `
      SELECT 
        v.chunk_index as chunk_id,
        c.content as text
      FROM fact_vectors v
      JOIN fact_articles a ON v.article_id = a.article_id
      JOIN fact_chunks c ON v.article_id = c.article_id AND v.chunk_index = c.chunk_index
      WHERE a.article_id = $1
    `;
    
    const result = await pool.query(query, [articleId]);
    
    return NextResponse.json({
      article_id: articleId,
      chunks: result.rows
    });
  } catch (error: any) {
    console.error("Database query error:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
