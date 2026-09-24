# Engineering text annotation

A billable service that turns a 2D image into engineering text annotations, matched to a caller-registered reference, and charges once for the image.

## Language

### Image and text

**Image**:
A 2D raster picture submitted by the caller, including a picture of an engineering drawing.
_Avoid_: CAD file, DWG, DXF, drawing file

**Text region**:
A four-corner area of text on an image, with an orientation.
_Avoid_: Bounding box, axis-aligned box, mask, keypoint

**Text class**:
The engineering category of a text region: dimension, tolerance, thread callout, surface finish, part tag, revision, sheet metadata, or note.
_Avoid_: Annotation type, geometry kind, label type

**Transcript**:
The text read from a region. The raw transcript is the recognizer output. The normalized transcript is the engineering-format correction of that output.
_Avoid_: OCR string, token

### Results

**Annotation**:
One text region together with its transcripts, text class, confidence, domain-validation score, and any reference match. An annotation is either released or held.
_Avoid_: Label, detection, box

**Released**:
An annotation returned to the caller without waiting for a person.
_Avoid_: Final, approved, billed annotation

**Held**:
An annotation withheld until the caller’s user accepts or edits it.
_Avoid_: Rejected, failed, dropped

**Review task**:
The caller’s work item for held annotations on an image. The caller’s user completes it.
_Avoid_: Labeling task, annotation job, queue item

### Reference and money

**Reference source**:
A caller-registered S3 JSON document, identified by a source id, whose entries annotations are matched against.
_Avoid_: Ground truth, database, template

**Match**:
A regex or fuzzy comparison of a normalized transcript to an entry in the reference source.
_Avoid_: Semantic match, embedding match, join

**Work level**:
How an image was processed: standard (one pass) or oriented (tiled, rectified, four-way recognition). Work level sets the price of the image.
_Avoid_: Tier, engine tier, SKU

**Engine**:
The text recognizer. This cut uses PaddleOCR.
_Avoid_: Tier, model tier

**Usage charge**:
The single charge for one image, recorded when detection finishes, priced by work level. Review does not add a charge.
_Avoid_: Per-annotation fee, review fee, tier price
