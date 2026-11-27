import { Button, Group, SimpleGrid, Text, Title } from '@mantine/core';
import {
  IconArrowRight,
  IconBuildingWarehouse,
  IconCalendarEvent,
  IconCash,
  IconCloudLock,
  IconDeviceMobile,
  IconFileInvoice,
  IconLock,
  IconMail,
  IconNotebook,
  IconPrinter,
  IconReceipt2,
  IconShieldCheck,
  IconUsers,
} from '@tabler/icons-react';

import { goTo } from '@/app/publicNav';

import { ContactButton, EMAIL } from './ContactButton';
import classes from './HomePage.module.css';
import { PublicFooter, PublicNav } from './PublicChrome';

/** What goes wrong in a busy agency, and what ChhapaKhata does about it. */
const PROBLEMS = [
  {
    icon: IconNotebook,
    before: 'Orders on paper slips and WhatsApp',
    after:
      'Every order in one place, priced as you type: size × rate, add-ons and the minimum charge.',
  },
  {
    icon: IconCash,
    before: '“How much did we charge him last time?”',
    after: 'A returning customer’s last rate fills itself in. No guessing, no arguments.',
  },
  {
    icon: IconReceipt2,
    before: 'Udhar in a notebook, then forgotten',
    after: 'Every customer’s khata: what they owe, since when, and a statement to send them.',
  },
  {
    icon: IconBuildingWarehouse,
    before: 'Flex rolls run out and nobody knows where they went',
    after: 'Stock by the roll: the square feet used on each job, and the waste.',
  },
  {
    icon: IconFileInvoice,
    before: 'Bills typed in Word, numbers skipped',
    after: 'IRD-style bills with PAN, VAT 13 % and gap-free numbers each fiscal year.',
  },
  {
    icon: IconUsers,
    before: 'Salary worked out by hand at month end',
    after: 'Daily attendance becomes salary by the Nepali month, with a slip to sign.',
  },
];

const STEPS = [
  {
    no: '01',
    title: 'Counter',
    text: 'Take the order. The price is there before the customer asks.',
  },
  {
    no: '02',
    title: 'Press',
    text: 'Follow each job to delivery, with the roll it was printed on.',
  },
  {
    no: '03',
    title: 'Bill',
    text: 'One click: a proper tax invoice, on A4, A5 or a 3-inch printer.',
  },
  {
    no: '04',
    title: 'Khata',
    text: 'Paid, part paid or udhar: the customer’s balance is always right.',
  },
];

const NEPAL = [
  {
    icon: IconCalendarEvent,
    title: 'Miti everywhere',
    text: 'A Nepali calendar on every date, AD beside it.',
  },
  {
    icon: IconCash,
    title: 'Lakh and crore',
    text: 'Rs. 1,20,000 written the way you read it, with amounts in words.',
  },
  {
    icon: IconReceipt2,
    title: 'eSewa, Khalti, Fonepay',
    text: 'Cash, bank, cheque, QR, advance or udhar.',
  },
  {
    icon: IconFileInvoice,
    title: 'Fiscal year from Shrawan',
    text: 'Bill numbers start again on 1 Shrawan.',
  },
];

const TRUST = [
  { icon: IconDeviceMobile, text: 'On the shop PC and on your phone' },
  { icon: IconLock, text: 'A personal login for each person' },
  { icon: IconShieldCheck, text: 'Your shop’s data seen by your shop only' },
  { icon: IconCloudLock, text: 'Backed up every night, encrypted' },
];

/** The page a visitor sees at the bare address before signing in. */
export function HomePage() {
  const signIn = () => goTo('/login');

  return (
    <div className={classes.page}>
      <PublicNav
        links={[
          { href: '#problem', label: 'Why' },
          { href: '#how', label: 'How it works' },
          { href: '#contact', label: 'Contact' },
        ]}
      />

      <main>
        {/* Hero ------------------------------------------------------------------------ */}
        <section className={`${classes.wrap} ${classes.hero}`}>
          <div className={classes.heroText}>
            <Text className={classes.eyebrow}>
              For advertising agencies and print shops in Nepal
            </Text>
            <Title order={1} className={classes.heroTitle}>
              Every job and every rupee, from counter to collection.
            </Title>
            <Text className={classes.lead}>
              <b>ChhapaKhata</b> (छापाखाता) is the account book for flex, banner, signboard and
              print work. Price a job by the square foot, bill it in Miti with VAT, and always know
              who still owes you.
            </Text>
            <Group gap="sm" mt={32} className={classes.ctas}>
              <ContactButton size="md" rightSection={<IconArrowRight size={18} />}>
                Get it for your shop
              </ContactButton>
              <Button size="md" variant="default" onClick={signIn}>
                Sign in
              </Button>
            </Group>
            <Text size="sm" c="dimmed" mt="md">
              Bikram Sambat · VAT 13 % · PC and phone
            </Text>
          </div>

          <div className={classes.heroArt} aria-hidden="true">
            <div className={classes.slot} />
            <div className={classes.feed}>
              <div className={classes.bill}>
                <div className={classes.cmyk}>
                  <span style={{ background: '#00AEEF' }} />
                  <span style={{ background: '#EC008C' }} />
                  <span style={{ background: '#FFF200' }} />
                  <span style={{ background: '#231F20' }} />
                </div>
                <div className={classes.billHead}>
                  <div>
                    <div className={classes.billKind}>TAX INVOICE</div>
                    <div className={classes.billNo}>INV-2083/84-0142</div>
                  </div>
                  <div className={classes.billDate}>
                    Miti 2083.08.11
                    <br />
                    Himal Tent House
                  </div>
                </div>
                <div className={classes.line}>
                  <span>
                    Star Flex
                    <small>6 × 3 ft · 18 sq ft × Rs 45</small>
                  </span>
                  <span>810.00</span>
                </div>
                <div className={classes.line}>
                  <span>
                    Eyelets
                    <small>8 pcs × Rs 10</small>
                  </span>
                  <span>80.00</span>
                </div>
                <div className={classes.sums}>
                  <span>Sub-total</span>
                  <span>890.00</span>
                  <span>VAT 13 %</span>
                  <span>115.70</span>
                </div>
                <div className={classes.total}>
                  <span>Total</span>
                  <span>Rs. 1,005.70</span>
                </div>
                <div className={classes.words}>One thousand five rupees and seventy paisa only</div>
                <div className={classes.stamp}>
                  <div>PAID</div>
                  <div className={classes.stampSub}>भुक्तानी भयो</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* The problem ------------------------------------------------------------------- */}
        <section id="problem" className={classes.section}>
          <div className={classes.wrap}>
            <div className={classes.sectionHead}>
              <Text className={classes.eyebrow}>The problem</Text>
              <Title order={2} className={classes.sectionTitle}>
                Busy shops lose money in small ways, every day.
              </Title>
              <Text c="dimmed" maw={560}>
                Not in one big mistake: in a rate quoted too low, an udhar nobody chased, a roll
                that went missing. ChhapaKhata closes those gaps.
              </Text>
            </div>
            <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="lg">
              {PROBLEMS.map(({ icon: Icon, before, after }) => (
                <div key={before} className={classes.problem}>
                  <span className={classes.problemIcon}>
                    <Icon size={20} stroke={1.75} />
                  </span>
                  <Text className={classes.before}>{before}</Text>
                  <Text className={classes.after}>{after}</Text>
                </div>
              ))}
            </SimpleGrid>
          </div>
        </section>

        {/* How a job moves ---------------------------------------------------------------- */}
        <section id="how" className={`${classes.section} ${classes.tinted}`}>
          <div className={classes.wrap}>
            <div className={classes.sectionHead}>
              <Text className={classes.eyebrow}>How it works</Text>
              <Title order={2} className={classes.sectionTitle}>
                One job, four stops, nothing written twice.
              </Title>
            </div>
            <ol className={classes.steps}>
              {STEPS.map((s) => (
                <li key={s.no} className={classes.step}>
                  <span className={classes.stepNo}>{s.no}</span>
                  <Text fw={700} size="lg">
                    {s.title}
                  </Text>
                  <Text c="dimmed" size="sm" mt={4}>
                    {s.text}
                  </Text>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Made for Nepal ---------------------------------------------------------------- */}
        <section className={classes.nepal}>
          <div className={classes.wrap}>
            <div className={classes.sectionHead}>
              <Text className={classes.eyebrowDark}>Made for Nepal</Text>
              <Title order={2} className={classes.sectionTitle} c="white">
                Built around how shops here actually work.
              </Title>
            </div>
            <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }} spacing="lg">
              {NEPAL.map(({ icon: Icon, title, text }) => (
                <div key={title} className={classes.nepalItem}>
                  <Icon size={22} stroke={1.75} className={classes.nepalIcon} />
                  <Text fw={600} c="white" mt="sm">
                    {title}
                  </Text>
                  <Text size="sm" c="slate.4" mt={4}>
                    {text}
                  </Text>
                </div>
              ))}
            </SimpleGrid>
            <div className={classes.trust}>
              {TRUST.map(({ icon: Icon, text }) => (
                <span key={text} className={classes.trustItem}>
                  <Icon size={16} stroke={1.75} />
                  {text}
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* Contact --------------------------------------------------------------------- */}
        <section id="contact" className={classes.section}>
          <div className={classes.wrap}>
            <div className={classes.contact}>
              <div className={classes.contactBar} aria-hidden="true" />
              <IconPrinter size={30} stroke={1.5} className={classes.contactIcon} />
              <Title order={2} className={classes.sectionTitle}>
                Run an advertising agency or a print shop?
              </Title>
              <Text c="dimmed" maw={520} mx="auto">
                Write to me. I will set ChhapaKhata up with your own rates, customers and old
                records, and show your staff how to use it.
              </Text>
              <ContactButton size="md" mt="xl" leftSection={<IconMail size={18} />}>
                Email me
              </ContactButton>
              <Text className={classes.email}>{EMAIL}</Text>
            </div>
          </div>
        </section>
      </main>

      <PublicFooter />
    </div>
  );
}
