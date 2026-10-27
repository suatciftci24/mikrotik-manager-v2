import type { ReactNode, Ref } from 'react';

/** Common module heading; uses existing page layout and mobile action wrapping. */
export function PageHeading({title, description, eyebrow, actions, headingRef}: {
  title: string; description: string; eyebrow: string; actions?: ReactNode; headingRef?: Ref<HTMLHeadingElement>;
}) {
  return <section className="page-heading-row"><div><div className="eyebrow">{eyebrow}</div><h1 ref={headingRef} tabIndex={headingRef ? -1 : undefined}>{title}</h1><p>{description}</p></div>{actions && <div className="heading-actions">{actions}</div>}</section>;
}
