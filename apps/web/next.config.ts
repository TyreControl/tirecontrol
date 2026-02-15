import type { NextConfig } from "next";

const isGithubActions = process.env.GITHUB_ACTIONS === "true";
const repository = process.env.GITHUB_REPOSITORY || "";
const repoName = repository.split("/")[1] || "";
const isUserOrOrgPage = repoName.endsWith(".github.io");
const basePath = isGithubActions && !isUserOrOrgPage ? `/${repoName}` : "";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  basePath,
  assetPrefix: basePath || undefined,
};

export default nextConfig;
