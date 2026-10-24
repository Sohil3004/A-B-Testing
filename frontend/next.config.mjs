/** @type {import('next').NextConfig} */
const nextConfig = {
  ...(process.env.VERCEL ? {} : { output: "standalone" }),
  async rewrites() {
    // On Vercel (or `vercel dev`), top-level rewrites in vercel.json route /api/* to the backend service.
    if (process.env.VERCEL) {
      return [];
    }
    const target = process.env.BACKEND_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${target.replace(/\/$/, "")}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
