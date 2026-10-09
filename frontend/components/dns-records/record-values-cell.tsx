"use client";

import Button from "@cloudscape-design/components/button";
import { useState } from "react";
import styles from "./dns-records.module.css";

export function RecordValuesCell({ values }: { values: string[] }) {
  const [expanded, setExpanded] = useState(false);
  const lengthy = values.length > 4 || values.some((value) => value.length > 240);
  const displayed = expanded || !lengthy ? values : values.slice(0, 2);
  return <div className={styles.values}>
    {displayed.map((value, index) => <div key={index}>{!expanded && lengthy && value.length > 240 ? `${value.slice(0, 240)}…` : value}</div>)}
    {!values.length && "—"}
    {lengthy && <Button variant="inline-link" onClick={() => setExpanded((value) => !value)}>
      {expanded ? "Show less" : values.length === 1 ? "Show full value" : "Show all values"}
    </Button>}
  </div>;
}
