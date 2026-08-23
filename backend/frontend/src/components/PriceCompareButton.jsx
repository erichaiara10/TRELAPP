import React from "react";
import AIPriceAnalysis from "@/components/AIPriceAnalysis";

/**
 * The single public Compare Price entry point.
 *
 * Keeping the subject-property mapping here ensures Home, Buy, Rent, Property
 * Details and Sell all submit the same applicable comparison fields and open
 * the same modal presentation.
 */
export default function PriceCompareButton({
  property,
  audience = "buyer",
  testIdPrefix = "price-compare",
  buttonClassName,
  buttonStyle,
  showIcon = true,
}) {
  const p = property || {};
  const propertyType = String(p.property_type || "");
  const isVacantLand = /(^|\s)(vacant\s+)?land($|\s)/i.test(propertyType);
  const isBuildingAreaRelevant = /(commercial|industrial|office|warehouse|retail)/i.test(propertyType);

  return (
    <AIPriceAnalysis
      property_id={p.id || p.property_id}
      variant="compact"
      buyerFacing={audience === "buyer"}
      audience={audience}
      property_type={p.property_type}
      listing_type={p.listing_type || "sale"}
      price={p.price}
      province={p.province}
      city={p.city || p.location}
      suburb={p.suburb}
      local_area={p.local_area}
      bedrooms={p.bedrooms}
      bathrooms={p.bathrooms}
      parking={p.parking}
      land_area_sqm={isVacantLand ? (p.land_area_sqm || (p.total_area_ha ? Number(p.total_area_ha) * 10000 : p.area_sqm)) : null}
      building_area_sqm={isBuildingAreaRelevant ? (p.building_area_sqm || p.floor_area_sqm || p.area_sqm) : null}
      property_condition={p.property_condition}
      tenure_type={p.tenure_type}
      street_name={p.street_name}
      nearby_landmark={p.nearby_landmark}
      testIdPrefix={testIdPrefix}
      buttonClassName={buttonClassName}
      buttonStyle={buttonStyle}
      showIcon={showIcon}
    />
  );
}
