// BirFatura Özel Entegrasyon ucu — yol BirFatura tarafından sabittir.
import { NextRequest } from "next/server";
import { birfaturaVekil } from "@/lib/birfatura";

export async function POST(req: NextRequest) {
  return birfaturaVekil(req, "paymentMethods");
}
