/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  compress: false,
  agentRules: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${process.env.API_PROXY_TARGET || "http://127.0.0.1:8000"}/api/:path*` }];
  },
};
export default nextConfig;
