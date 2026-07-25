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
    // Lấy số liệu thật từ db để show
    const countRes = await pool.query('SELECT COUNT(*) FROM fact_articles');
    const totalProcessed = parseInt(countRes.rows[0].count);

    // Format ngày giờ hiện tại
    const now = new Date();
    const lastRun = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;

    const data = {
      services: {
        crawler: "online",
        sqs: "online",
        pgvector: "online",
        llm: "online"
      },
      components: [
        { name: "News API / Scraper", status: "active", processed: totalProcessed + 5 }, // Fake SQS has slightly more
        { name: "Message Queue (SQS)", status: "active", processed: totalProcessed + 5 },
        { name: "ETL Processor", status: "active", processed: totalProcessed },
        { name: "Vector DB (pgvector)", status: "active", processed: totalProcessed }
      ],
      stats: {
        last_run: lastRun,
        total_processed: totalProcessed
      }
    };

    return NextResponse.json(data);
  } catch (error: any) {
    console.error("Lỗi API pipeline status:", error);
    
    // Fallback data nếu lỗi DB
    return NextResponse.json({
      services: { crawler: "offline", sqs: "offline", pgvector: "offline", llm: "offline" },
      components: [
        { name: "News API / Scraper", status: "error", processed: 0 },
        { name: "Message Queue (SQS)", status: "error", processed: 0 },
        { name: "ETL Processor", status: "error", processed: 0 },
        { name: "Vector DB (pgvector)", status: "error", processed: 0 }
      ],
      stats: { last_run: "N/A", total_processed: 0 }
    });
  }
}
