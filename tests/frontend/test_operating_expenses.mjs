import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {mkdtempSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const root = resolve(import.meta.dirname, '../..');
const directory = mkdtempSync(join(tmpdir(), 'restaurantos-expense-money-'));
try {
  execFileSync(process.execPath, [join(root,'node_modules/typescript/bin/tsc'), '--target','ES2022','--module','NodeNext','--moduleResolution','NodeNext','--outDir',directory,join(root,'apps/admin-web/src/features/expenses/expenseState.ts')]);
  const {expenseCents, expenseMethods} = await import(pathToFileURL(join(directory,'expenseState.js')));
  for (const [value,cents] of [['0.29',29],['300',30000],['20.1',2010],['21474836.47',2147483647],['0',0]]) assert.equal(expenseCents(value), cents);
  for (const value of ['-1','1.001','1e3','NaN','Infinity','21474836.48','','1,000','9007199254740999']) assert.throws(()=>expenseCents(value));
  assert.deepEqual(Object.keys(expenseMethods), ['cash','transfer','card','other']);
  console.log('EXP-001 exact cents and method contract: passed');
} finally {rmSync(directory,{recursive:true,force:true});}
