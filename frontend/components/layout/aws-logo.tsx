import Image from "next/image";

export const AWS_LOGO = { src: "/aws-logo.svg", alt: "AWS" };

export function AwsLogo() {
  return <Image src={AWS_LOGO.src} alt={AWS_LOGO.alt} width={44} height={26} className="console-identity" />;
}
