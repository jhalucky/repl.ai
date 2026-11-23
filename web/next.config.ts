import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      {
        source: "/founder",
        destination: "/register?plan=founder",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
