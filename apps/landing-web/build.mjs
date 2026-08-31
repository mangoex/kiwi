import { cp, rm } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const packageRoot = dirname(fileURLToPath(import.meta.url));
const source = join(packageRoot, 'src');
const destination = join(packageRoot, 'dist');

await rm(destination, { force: true, recursive: true });
await cp(source, destination, { recursive: true });
