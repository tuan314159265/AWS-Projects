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
    // 1. Total Articles
    const articlesRes = await pool.query('SELECT COUNT(*) FROM fact_articles');
    const total_articles = parseInt(articlesRes.rows[0].count);

    // 2. Total Vectors
    const vectorsRes = await pool.query('SELECT COUNT(*) FROM fact_vectors');
    const total_vectors = parseInt(vectorsRes.rows[0].count);

    // 3. Top Authors
    const topAuthorsRes = await pool.query(`
      SELECT au.author_name as name, COUNT(faa.article_id) as count
      FROM fact_article_authors faa
      JOIN dim_author au ON faa.author_id = au.author_id
      GROUP BY au.author_name
      ORDER BY count DESC
      LIMIT 5
    `);
    const top_authors = topAuthorsRes.rows.map(row => ({
      name: row.name,
      count: parseInt(row.count),
      percent: Math.round((parseInt(row.count) / (total_articles || 1)) * 100)
    }));

    // 4. Source Distribution
    const sourceRes = await pool.query(`
      SELECT s.domain as name, COUNT(a.article_id) as value
      FROM fact_articles a
      JOIN dim_source s ON a.source_id = s.source_id
      GROUP BY s.domain
      ORDER BY value DESC
    `);
    const source_distribution = sourceRes.rows.map(row => ({
      name: row.name,
      value: parseInt(row.value),
      percent: Math.round((parseInt(row.value) / (total_articles || 1)) * 100)
    }));

    // 5. Trend Data
    const trendRes = await pool.query(`
      SELECT t.date as date, COUNT(a.article_id) as count
      FROM fact_articles a
      JOIN dim_time t ON a.time_id = t.time_id
      GROUP BY t.date
      ORDER BY t.date ASC
      LIMIT 7
    `);
    const trend_data = trendRes.rows.map(row => ({
      date: new Date(row.date).toLocaleDateString('vi-VN'),
      count: parseInt(row.count)
    }));

    // 6. Latest Articles
    const latestRes = await pool.query(`
      SELECT a.title, s.domain as source, t.date
      FROM fact_articles a
      JOIN dim_source s ON a.source_id = s.source_id
      JOIN dim_time t ON a.time_id = t.time_id
      ORDER BY a.article_id DESC
      LIMIT 10
    `);
    const latest_articles = latestRes.rows.map(row => ({
      title: row.title,
      source: row.source,
      date: new Date(row.date).toLocaleDateString('vi-VN')
    }));

    return NextResponse.json({
      total_articles,
      total_sources: source_distribution.length,
      total_vectors,
      top_authors,
      source_distribution,
      trend_data,
      latest_articles
    });
  } catch (error: any) {
    console.error("Database query error:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
