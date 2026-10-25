import type { NextConfig } from "next";

// Static export for GitHub Pages: https://<owner>.github.io/png-to-svg-vectorize/ (BASE_PATH="" for a custom domain).
const basePath = process.env.BASE_PATH ?? "/png-to-svg-vectorize";

const nextConfig: NextConfig = {
  output: "export",
  basePath,
  trailingSlash: true,
  poweredByHeader: false,
  images: { unoptimized: true },
  env: { NEXT_PUBLIC_BASE_PATH: basePath },
  // first-time visitors on a marketing site: inline the (atomic, small) CSS instead of a render-blocking request
  experimental: { inlineCss: true },
};

export default nextConfig;
