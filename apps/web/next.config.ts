import type { NextConfig } from "next";

const nextConfig: NextConfig = {
    output: 'export',
    // basePath: '/tirecontrol', // Enable this if deploying to https://username.github.io/tirecontrol
    images: {
        unoptimized: true,
    },
};

export default nextConfig;
