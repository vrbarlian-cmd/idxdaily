import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

// Top Indonesian stocks by market cap
const topIDXTickers = [
  { symbol: 'BBCA', name: 'Bank Central Asia Tbk', sector: 'Financial', subsector: 'Banking' },
  { symbol: 'BBRI', name: 'Bank Rakyat Indonesia Tbk', sector: 'Financial', subsector: 'Banking' },
  { symbol: 'BMRI', name: 'Bank Mandiri Tbk', sector: 'Financial', subsector: 'Banking' },
  { symbol: 'TLKM', name: 'Telkom Indonesia Tbk', sector: 'Infrastructure', subsector: 'Telecommunication' },
  { symbol: 'ASII', name: 'Astra International Tbk', sector: 'Miscellaneous Industry', subsector: 'Automotive' },
  { symbol: 'BBNI', name: 'Bank Negara Indonesia Tbk', sector: 'Financial', subsector: 'Banking' },
  { symbol: 'AMMN', name: 'Amman Mineral Internasional Tbk', sector: 'Mining', subsector: 'Metal and Mineral Mining' },
  { symbol: 'UNVR', name: 'Unilever Indonesia Tbk', sector: 'Consumer Goods', subsector: 'Household' },
  { symbol: 'ADRO', name: 'Adaro Energy Indonesia Tbk', sector: 'Mining', subsector: 'Coal Mining' },
  { symbol: 'GOTO', name: 'GoTo Gojek Tokopedia Tbk', sector: 'Technology', subsector: 'Internet' },
  { symbol: 'ITMG', name: 'Indo Tambangraya Megah Tbk', sector: 'Mining', subsector: 'Coal Mining' },
  { symbol: 'INDF', name: 'Indofood Sukses Makmur Tbk', sector: 'Consumer Goods', subsector: 'Food & Beverage' },
  { symbol: 'ICBP', name: 'Indofood CBP Sukses Makmur Tbk', sector: 'Consumer Goods', subsector: 'Food & Beverage' },
  { symbol: 'PGAS', name: 'Perusahaan Gas Negara Tbk', sector: 'Infrastructure', subsector: 'Energy' },
  { symbol: 'PTBA', name: 'Bukit Asam Tbk', sector: 'Mining', subsector: 'Coal Mining' },
  { symbol: 'SMGR', name: 'Semen Indonesia Tbk', sector: 'Basic Industry', subsector: 'Cement' },
  { symbol: 'INCO', name: 'Vale Indonesia Tbk', sector: 'Mining', subsector: 'Metal and Mineral Mining' },
  { symbol: 'ANTM', name: 'Aneka Tambang Tbk', sector: 'Mining', subsector: 'Metal and Mineral Mining' },
  { symbol: 'CPIN', name: 'Charoen Pokphand Indonesia Tbk', sector: 'Basic Industry', subsector: 'Animal Feed' },
  { symbol: 'MDKA', name: 'Merdeka Copper Gold Tbk', sector: 'Mining', subsector: 'Metal and Mineral Mining' },
  { symbol: 'KLBF', name: 'Kalbe Farma Tbk', sector: 'Consumer Goods', subsector: 'Pharmaceuticals' },
  { symbol: 'MNCN', name: 'Media Nusantara Citra Tbk', sector: 'Consumer Goods', subsector: 'Advertising' },
  { symbol: 'EMTK', name: 'Elang Mahkota Teknologi Tbk', sector: 'Consumer Goods', subsector: 'Media' },
  { symbol: 'BYAN', name: 'Bayan Resources Tbk', sector: 'Mining', subsector: 'Coal Mining' },
  { symbol: 'MEDC', name: 'Medco Energi Internasional Tbk', sector: 'Mining', subsector: 'Oil & Gas' },
];

async function main() {
  console.log('Start seeding...');

  for (const ticker of topIDXTickers) {
    await prisma.ticker.upsert({
      where: { symbol: ticker.symbol },
      update: {},
      create: ticker,
    });
    console.log(`Created/Updated ticker: ${ticker.symbol}`);
  }

  console.log('Seeding finished.');
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
