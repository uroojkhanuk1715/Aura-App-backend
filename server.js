'use strict';
const cfg = require('./lib/config');
const { createServer } = require('./lib/app');

if (cfg.prod && cfg.fakeTopup) throw new Error('ALLOW_FAKE_TOPUP must not be set in production.');
const server = createServer();
server.listen(cfg.port, () => console.log(`[aura] listening on :${cfg.port} (${cfg.prod ? 'production' : 'development'})`));

for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => { server.close(() => process.exit(0)); setTimeout(() => process.exit(0), 5000).unref(); });
process.on('unhandledRejection', e => console.error('[aura] unhandledRejection', e));
