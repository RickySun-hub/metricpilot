const basePath = process.env.METRICPILOT_BASE_PATH || '';
if (basePath && (!basePath.startsWith('/') || basePath.endsWith('/'))) {
  throw new Error('METRICPILOT_BASE_PATH must start with / and have no trailing slash.');
}
const nextConfig = {
  agentRules: false,
  output: 'export',
  basePath,
  env: { NEXT_PUBLIC_BASE_PATH: basePath, NEXT_PUBLIC_SOURCE_REF: process.env.METRICPILOT_SOURCE_REF || 'main' },
  async rewrites() {
    const backend = process.env.METRICPILOT_API_URL;
    return backend ? [{ source: '/api/:path*', destination: `${backend.replace(/\/$/, '')}/api/:path*` }] : [];
  },
};
export default nextConfig;
