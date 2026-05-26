#!/usr/bin/env node

/**
 * Setup script for IDX Terminal
 * Run with: node scripts/setup.js
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

function question(query) {
  return new Promise(resolve => rl.question(query, resolve));
}

function exec(command, description) {
  console.log(`\n📦 ${description}...`);
  try {
    execSync(command, { stdio: 'inherit' });
    console.log(`✅ ${description} complete`);
    return true;
  } catch (error) {
    console.error(`❌ ${description} failed:`, error.message);
    return false;
  }
}

async function main() {
  console.log('🚀 IDX Terminal Setup\n');
  console.log('This script will help you set up the application.\n');

  // Check if .env exists
  const envPath = path.join(process.cwd(), '.env');
  let needsEnv = !fs.existsSync(envPath);

  if (needsEnv) {
    console.log('📝 Setting up environment variables...\n');
    const apiKey = await question('Enter your OpenAI API key: ');
    
    const envContent = `DATABASE_URL="file:./dev.db"
OPENAI_API_KEY="${apiKey}"
NODE_ENV="development"
NEXT_PUBLIC_APP_URL="http://localhost:3000"
`;
    
    fs.writeFileSync(envPath, envContent);
    console.log('✅ .env file created');
  } else {
    console.log('✅ .env file already exists');
  }

  // Install dependencies
  if (!exec('npm install', 'Installing dependencies')) {
    process.exit(1);
  }

  // Setup database
  if (!exec('npx prisma db push', 'Setting up database')) {
    process.exit(1);
  }

  // Seed database
  if (!exec('npm run db:seed', 'Seeding database with Indonesian tickers')) {
    process.exit(1);
  }

  console.log('\n✨ Setup complete!\n');
  console.log('To start the development server, run:');
  console.log('  npm run dev\n');
  console.log('Then open http://localhost:3000 in your browser.\n');

  rl.close();
}

main().catch(error => {
  console.error('Setup failed:', error);
  process.exit(1);
});
