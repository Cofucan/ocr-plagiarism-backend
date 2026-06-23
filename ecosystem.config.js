module.exports = {
  apps: [
    {
      name: "ocr-api",
      cwd: "/var/www/apps/proj/ocr-plagiarism-backend",
      script: "/var/www/apps/proj/ocr-plagiarism-backend/.venv/bin/uvicorn",
      args: "main:app --host 127.0.0.1 --port 8017 --workers 2",
      interpreter: "none",
      exec_mode: "fork",
      env: {
        PYTHONUNBUFFERED: "1",
        // Optional: override .env values here if needed
        // DEBUG: "false",
        // APP_VERSION: "1.0.0"
      },
      autorestart: true,
      max_memory_restart: "512M",
      out_file: "/var/log/pm2/ocr-api.out.log",
      error_file: "/var/log/pm2/ocr-api.err.log",
      time: true
    }
  ]
};
