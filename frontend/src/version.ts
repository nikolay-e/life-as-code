// Version information injected at build time
// Global constants are defined in vite.config.ts via define plugin
// TypeScript declarations are in vite-env.d.ts

export const version = {
  version: __APP_VERSION__,
  buildDate: __BUILD_DATE__,
  commitSha: __COMMIT_SHA__,
  short: __APP_VERSION__.split("-")[1] || __APP_VERSION__,
};

// Log version info on app startup
console.log(`Life-as-Code v${version.version}`);
console.log(`Built: ${version.buildDate}`);
console.log(`Commit: ${version.short}`);

export default version;
