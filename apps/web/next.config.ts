import type { NextConfig } from "next";

const nextConfig: NextConfig = {
    output: 'export',
    basePath: '/tirecontrol',
    images: {
        unoptimized: true,
    },
};

export default nextConfig;
