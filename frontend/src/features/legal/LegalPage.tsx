import { Anchor } from '@mantine/core';
import { type ReactNode, useEffect } from 'react';

import { goTo } from '@/app/publicNav';

import { EMAIL } from '../home/ContactButton';
import { PublicFooter, PublicNav } from '../home/PublicChrome';
import classes from './LegalPage.module.css';

const UPDATED = '27 November 2026';
const PROVIDER = 'Prashanna Chauhan Kshetri';

function Email() {
  return (
    <Anchor href={`mailto:${EMAIL}`} fz="inherit" style={{ overflowWrap: 'anywhere' }}>
      {EMAIL}
    </Anchor>
  );
}

function PageLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Anchor
      component="button"
      onClick={() => goTo(to)}
      fz="inherit"
      style={{ verticalAlign: 'baseline' }}
    >
      {children}
    </Anchor>
  );
}

function LegalLayout({ title, children }: { title: string; children: ReactNode }) {
  useEffect(() => {
    const before = document.title;
    document.title = `${title} · ChhapaKhata`;
    return () => {
      document.title = before;
    };
  }, [title]);
  return (
    <div className={classes.page}>
      <PublicNav />
      <main className={classes.article}>
        <h1>{title}</h1>
        <p className={classes.updated}>Last updated {UPDATED}</p>
        {children}
      </main>
      <PublicFooter />
    </div>
  );
}

export function TermsPage() {
  return (
    <LegalLayout title="Terms of service">
      <div className={classes.summary}>
        <p>
          <b>In short:</b> your shop’s records are yours. We keep them safe, private and backed up,
          and you can take them out at any time. You are responsible for what you enter, including
          the rates, VAT and the bills you give your customers.
        </p>
      </div>

      <h2>1. Who we are</h2>
      <p>
        ChhapaKhata is print shop management software made in Nepal and provided by {PROVIDER}{' '}
        (“we”). You can reach us at <Email />. “You” means the shop or business that uses
        ChhapaKhata, and the people it gives a login to.
      </p>

      <h2>2. The service</h2>
      <p>
        ChhapaKhata is a web app for orders, production, bills, payments, customer accounts, stock,
        staff attendance and salary, and reports. A shop starts using it after agreeing the price
        and setup with us. We may improve or change features over time; we will not remove a feature
        your shop relies on without telling you first.
      </p>

      <h2>3. Accounts</h2>
      <ul>
        <li>Each person gets their own login. Keep your password to yourself.</li>
        <li>
          The shop’s owner decides who has a login and what each one may do, and is responsible for
          the use of those logins.
        </li>
        <li>
          Tell us straight away if you think someone else has used your login. Signing in is locked
          for a while after several wrong passwords, to protect you.
        </li>
      </ul>

      <h2>4. Your data</h2>
      <ul>
        <li>
          Your shop’s records (customers, orders, bills, payments, stock, staff and the rest) belong
          to your shop. We use them only to run ChhapaKhata for you and to help when you ask for
          support.
        </li>
        <li>
          The owner can export the data at any time (Settings → Backups &amp; export). If you stop
          using ChhapaKhata, we give you a final export on request and then delete your shop’s data;
          copies in backups are removed as those backups expire (see the{' '}
          <PageLink to="/privacy">privacy policy</PageLink>).
        </li>
        <li>
          If you enter details of your own customers or staff, make sure you are allowed to keep
          them, as the law in Nepal requires.
        </li>
      </ul>

      <h2>5. Bills and tax</h2>
      <p>
        ChhapaKhata prepares bills and receipts from what you enter: rates, discounts, VAT, PAN and
        dates. You are responsible for checking that they are correct and for your tax returns.
        ChhapaKhata is not approved by the Inland Revenue Department as electronic billing software
        unless we tell you so in writing; ask your auditor what your business needs.
      </p>

      <h2>6. Fees</h2>
      <p>
        Fees are as agreed with your shop in writing (for example in your proposal or invoice). If a
        fee is not paid, we will remind you first; after that we may pause the service. Pausing
        never deletes your data, and you can still ask for an export.
      </p>

      <h2>7. Availability and backups</h2>
      <p>
        We work to keep ChhapaKhata running and back it up every night, but no online service can
        promise never to stop. Planned work is done outside shop hours where possible. We recommend
        the owner keeps an export from time to time as well.
      </p>

      <h2>8. Fair use</h2>
      <p>
        Do not use ChhapaKhata for anything unlawful, try to get into another shop’s data or our
        systems, overload it on purpose, or resell it without our agreement.
      </p>

      <h2>9. Responsibility</h2>
      <p>
        We are not responsible for losses that come from wrong entries, from a login shared or left
        signed in, or from events outside our control. Where we are responsible, our total liability
        is limited to the fees your shop paid us in the twelve months before the problem.
      </p>

      <h2>10. Changes to these terms</h2>
      <p>
        If we change these terms in a way that matters, we will tell the shop’s owner by email or in
        the app before the change applies.
      </p>

      <h2>11. Law</h2>
      <p>
        These terms are governed by the laws of Nepal. We will try to settle any disagreement by
        talking first; otherwise it goes to the courts of Nepal.
      </p>
    </LegalLayout>
  );
}

export function PrivacyPage() {
  return (
    <LegalLayout title="Privacy policy">
      <div className={classes.summary}>
        <p>
          <b>In short:</b> we keep only what a print shop needs to run, we never sell it or use it
          for advertising, there is no tracking on this site, and each shop sees only its own data.
        </p>
      </div>

      <h2>1. Who is responsible</h2>
      <p>
        ChhapaKhata is provided by {PROVIDER}, Nepal (<Email />
        ). Each shop decides what it records about its own customers and staff and is responsible
        for that information; we keep it safe and use it only to run ChhapaKhata for the shop.
      </p>

      <h2>2. What is kept</h2>
      <ul>
        <li>
          <b>Logins:</b> name, username, phone (if given), role, and the password, stored only as a
          one-way hash that nobody can read back. Sign-ins are recorded with the date, time and
          internet address, for security.
        </li>
        <li>
          <b>What a shop enters:</b> its customers (name, phone, address, PAN), orders, bills,
          payments, stock, suppliers, and its staff’s attendance, salary and advances.
        </li>
        <li>
          <b>Activity log:</b> who changed what and when, so the owner can check the records.
        </li>
        <li>
          <b>Visitors to this site:</b> nothing beyond the usual server logs (internet address,
          browser, time), kept briefly to keep the service secure. There is no analytics, no
          advertising and no tracking.
        </li>
      </ul>

      <h2>3. Why</h2>
      <p>
        To run ChhapaKhata for the shop, keep it secure (for example locking sign-in after wrong
        passwords and limiting floods of requests), back it up, and help when the shop asks for
        support. We do not sell data, share it for marketing, or use it to train AI.
      </p>

      <h2>4. Where it is kept and who helps</h2>
      <ul>
        <li>
          The service runs on Amazon Web Services in Mumbai, India, behind Cloudflare, which
          protects and speeds up the connection. Everything travels encrypted (HTTPS).
        </li>
        <li>
          When the online backup copy is turned on, it is encrypted on our server before it is
          stored with a cloud storage provider, so they cannot read it.
        </li>
        <li>If you email us, your message is handled by our email provider (Gmail).</li>
      </ul>

      <h2>5. Each shop’s data stays apart</h2>
      <p>
        One ChhapaKhata can serve several shops. The database itself refuses to show one shop’s
        records to another, and within a shop each person sees only what their role allows.
      </p>

      <h2>6. How long</h2>
      <ul>
        <li>A shop’s data is kept while the shop uses ChhapaKhata.</li>
        <li>
          Backups are kept for up to 12 months (daily for two weeks, weekly for two months, monthly
          for a year), so something deleted can remain in an older backup until it expires.
        </li>
        <li>When a shop leaves, its data is deleted after a final export, as in the terms.</li>
      </ul>

      <h2>7. Cookies and data on your device</h2>
      <p>ChhapaKhata uses only what it needs to work. There are no third-party cookies.</p>
      <ul>
        <li>
          <code>sessionid</code>: keeps you signed in (ends after 12 hours without use, or when you
          sign out).
        </li>
        <li>
          <code>csrftoken</code>: protects your forms from being sent by another website.
        </li>
        <li>
          On the device (browser storage): a copy of the data you last saw, so the app opens fast
          and still shows it if the connection drops (removed when you sign out); your text size;
          and whether you have seen the cookie note.
        </li>
      </ul>

      <h2>8. Keeping it safe</h2>
      <p>
        Encrypted connections, hashed passwords, a lock after wrong passwords, limits on repeated
        requests, separate logins with roles, an activity log, and nightly backups with an encrypted
        online copy.
      </p>

      <h2>9. Your rights</h2>
      <p>
        Under Nepal’s Privacy Act, 2075 (2018), you can ask to see the personal information kept
        about you, have it corrected, or have it deleted where the law allows. If you are a customer
        or worker of a shop, please ask that shop first; it controls its records. Otherwise write to{' '}
        <Email />.
      </p>

      <h2>10. Changes</h2>
      <p>
        If this policy changes in a way that matters, we will update the date above and tell each
        shop’s owner. See also the <PageLink to="/terms">terms of service</PageLink>.
      </p>
    </LegalLayout>
  );
}
