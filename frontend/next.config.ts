import type { NextConfig } from "next";

// This value stays on the server. Rebuild when changing the rewrite target.
const proxyTarget = process.env.API_PROXY_TARGET;
let proxyOrigin: string | undefined;
if (proxyTarget) {
  const url = new URL(proxyTarget);
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username || url.password || url.search || url.hash ||
    url.pathname !== "/"
  ) {
    throw new Error("API_PROXY_TARGET must be an HTTP(S) origin without credentials or a path.");
  }
  proxyOrigin = url.origin;
}

const nextConfig: NextConfig = {
  transpilePackages: [
    "@cloudscape-design/components",
    "@cloudscape-design/component-toolkit",
  ],
  async rewrites() {
    return proxyOrigin
      ? [{ source: "/api/:path*", destination: `${proxyOrigin}/api/:path*` }]
      : [];
  },
};

export default nextConfig;
