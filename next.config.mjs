const nextConfig = {
  agentRules: false,
  output: 'export',
  async rewrites() {
    const backend = process.env.METRICPILOT_API_URL;
    return backend ? [{ source: '/api/:path*', destination: `${backend.replace(/\/$/, '')}/api/:path*` }] : [];
  },
};
export default nextConfig;
