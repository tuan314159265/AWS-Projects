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

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const limit = parseInt(searchParams.get('limit') || '50');
    const offset = parseInt(searchParams.get('offset') || '0');
    const q = searchParams.get('q') || '';
    const sourceParam = searchParams.get('source') || '';

    let query = `
      SELECT 
        a.article_id as id,
        a.title,
        am.url,
        s.domain as source,
        t.date as published_date,
        string_agg(DISTINCT au.author_name, ', ') as author,
        SUBSTRING(c.content, 1, 150) as snippet
      FROM fact_articles a
      LEFT JOIN article_metadata am ON a.url_hash = am.url_hash
      LEFT JOIN dim_source s ON a.source_id = s.source_id
      LEFT JOIN dim_time t ON a.time_id = t.time_id
      LEFT JOIN dim_content c ON a.content_id = c.content_id
      LEFT JOIN fact_article_authors faa ON a.article_id = faa.article_id
      LEFT JOIN dim_author au ON faa.author_id = au.author_id
      WHERE 1=1
    `;
    
    const values: any[] = [];
    let paramIndex = 1;

    if (q) {
      query += ` AND a.title ILIKE $${paramIndex}`;
      values.push(`%${q}%`);
      paramIndex++;
    }

    if (sourceParam && sourceParam !== 'All Sources') {
      query += ` AND s.domain = $${paramIndex}`;
      values.push(sourceParam);
      paramIndex++;
    }
    
    query += ` GROUP BY a.article_id, a.title, am.url, s.domain, t.date, c.content ORDER BY t.date DESC NULLS LAST LIMIT $${paramIndex} OFFSET $${paramIndex + 1}`;
    values.push(limit);
    values.push(offset);

    const result = await pool.query(query, values);
    return NextResponse.json(result.rows);
  } catch (error: any) {
    console.error("Database query error:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
