# Microsoft protocol specifications

The Open Specifications [remotex](https://github.com/andrewtheguy/remotex)'s RDP
client (`src/rdp_client/`) is written against, kept here as the PDFs Microsoft
publishes, because a published revision can change or its download link can move,
and as Markdown, because a PDF has to be converted to text every time it is read.
Microsoft's own page for each spec is the canonical source and lists every earlier
revision; check it before relying on a detail here being current. FreeRDP remains
the reference for what a real Windows host does where a spec is silent or wrong —
see [The RDP client, written here](https://github.com/andrewtheguy/remotex/blob/main/docs/rdp-client.md).

| Spec | Title | Used for | Release | Copy |
| --- | --- | --- | --- | --- |
| [MS-RDPBCGR][bcgr] | Basic Connectivity and Graphics Remoting | Connection sequence, capabilities, client info, fast-path input, static channels | March 9, 2026 | [PDF](MS-RDPBCGR.pdf) · [Markdown](MS-RDPBCGR.md) |
| [MS-CSSP][cssp] | Credential Security Support Provider (CredSSP) Protocol | NLA | April 23, 2024 | [PDF](MS-CSSP.pdf) · [Markdown](MS-CSSP.md) |
| [MS-RDPEDYC][edyc] | Dynamic Channel Virtual Channel Extension | `drdynvc` transport | April 23, 2024 | [PDF](MS-RDPEDYC.pdf) · [Markdown](MS-RDPEDYC.md) |
| [MS-RDPEGFX][egfx] | Graphics Pipeline Extension | Surfaces, caches, ClearCodec, RemoteFX Progressive | May 11, 2026 | [PDF](MS-RDPEGFX.pdf) · [Markdown](MS-RDPEGFX.md) |
| [MS-RDPRFX][rfx] | RemoteFX Codec Extension | The wavelet and color conversion Progressive builds on | April 23, 2024 | [PDF](MS-RDPRFX.pdf) · [Markdown](MS-RDPRFX.md) |
| [MS-RDPNSC][nsc] | NSCodec Extension | ClearCodec's NSCodec subcodec | April 23, 2024 | [PDF](MS-RDPNSC.pdf) · [Markdown](MS-RDPNSC.md) |
| [MS-RDPEGDI][egdi] | Graphics Device Interface (GDI) Acceleration Extensions | Planar codec | April 23, 2024 | [PDF](MS-RDPEGDI.pdf) · [Markdown](MS-RDPEGDI.md) |
| [MS-RDPEDISP][edisp] | Display Update Virtual Channel Extension | Resize | April 23, 2024 | [PDF](MS-RDPEDISP.pdf) · [Markdown](MS-RDPEDISP.md) |
| [MS-RDPEI][ei] | Input Virtual Channel Extension | Touch passthrough | April 23, 2024 | [PDF](MS-RDPEI.pdf) · [Markdown](MS-RDPEI.md) |
| [MS-RDPECLIP][eclip] | Clipboard Virtual Channel Extension | Clipboard | April 23, 2024 | [PDF](MS-RDPECLIP.pdf) · [Markdown](MS-RDPECLIP.md) |
| [MS-RDPEA][ea] | Audio Output Virtual Channel Extension | Sound | April 23, 2024 | [PDF](MS-RDPEA.pdf) · [Markdown](MS-RDPEA.md) |
| [MS-RDPEFS][efs] | File System Virtual Channel Extension | The `rdpdr` channel sound redirection needs | April 23, 2024 | [PDF](MS-RDPEFS.pdf) · [Markdown](MS-RDPEFS.md) |
| [MS-RDPECAM][ecam] | Video Capture Virtual Channel Extension | Camera redirection | April 23, 2024 | [PDF](MS-RDPECAM.pdf) · [Markdown](MS-RDPECAM.md) |
| [MS-RDPEAI][eai] | Audio Input Redirection Virtual Channel Extension | Microphone redirection | April 23, 2024 | [PDF](MS-RDPEAI.pdf) · [Markdown](MS-RDPEAI.md) |

The release date is the one printed on each PDF's title page.

## Markdown copies

`MS-XXX.md` is the same revision as `MS-XXX.pdf`, one file per spec, built by
[`tools/learn2md.py`](tools/learn2md.py) from the edition Microsoft Learn serves:
one HTML page per section, generated from the same source as the PDF. Read and
search these; the PDF is what to cite.

- Every section heading carries its number (`##### 2.2.1.5 RDPGFX_HEADER`), so
  `grep -n '^#* 2.2.1.5 ' MS-RDPEGFX.md` finds a section, and the contents list
  at the top of each file links to all of them.
- Bit-field diagrams are drawn as text, the way RFCs draw them. Learn's own
  Markdown output drops the field widths from them, which is why the converter
  works from the HTML.
- Figures are in `images/MS-XXX/`, referenced in place with Microsoft's alt text.
- Section references link within the file, references to another spec kept here
  link to its Markdown copy, and anything else links to Learn.

When these were generated, the words in the body of each file (sections 1 to the
index) were counted against the text of its PDF, and they agree to within 0.2%:
what differs is the table headers the PDF repeats at page breaks and the
occasional word a diagram cell wraps differently. Not carried over are the PDF's
revision history table and page numbers, which the Learn edition does not have.

For a spec not kept here,
[awakecoding/openspecs](https://github.com/awakecoding/openspecs) converts the
whole Windows Protocols corpus to Markdown from the DOCX files.

## Refreshing a copy

Each spec's page links its current PDF and DOCX under "Published Version". With
[uv](https://docs.astral.sh/uv/) installed, this downloads the current PDF and
rebuilds the Markdown and figures from the current pages:

```sh
uv run tools/learn2md.py --refresh --pdf MS-RDPEGFX
```

It prints the revision and release date it found; update the table with them.
Naming a spec that is not here yet adds it. Without `--refresh` the pages cached
in `.cache/learn/` are converted again, which is what to run after changing the
converter; with no spec named, every spec is built.

The PDFs are served from `https://winprotocoldocs-bhdugrdyduf5h2e4.b02.azurefd.net/`,
and the current PDF of a spec is at a stable name there:

```sh
curl -fL -o MS-RDPEGFX.pdf \
  'https://winprotocoldocs-bhdugrdyduf5h2e4.b02.azurefd.net/MS-RDPEGFX/%5bMS-RDPEGFX%5d.pdf'
```

The older `winprotocoldoc.blob.core.windows.net` archive links answer HTTP 409.

[bcgr]: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdpbcgr/5073f4ed-1e93-45e1-b039-6e30c385867c
[cssp]: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-cssp/85f57821-40bb-46aa-bfcb-ba9590b8fc30
[edyc]: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdpedyc/3bd53020-9b64-4c9a-97fc-90a79e7e1e06
[egfx]: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdpegfx/da5c75f9-cd99-450c-98c4-014a496942b0
[rfx]: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdprfx/62495a4a-a495-46ea-b459-5cde04c44549
[nsc]: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdpnsc/543fd1f1-8074-4122-8944-1017261810ca
[egdi]: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdpegdi/745f2eee-d110-464c-8aca-06fc1814f6ad
[edisp]: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdpedisp/d2954508-f487-48bc-8731-39743e0854a9
[ei]: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdpei/72a8cb65-7f6c-407c-a21a-3d970721fed0
[eclip]: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdpeclip/fb9b7e0b-6db4-41c2-b83c-f889c1ee7688
[ea]: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdpea/bea2d5cf-e3b9-4419-92e5-0e074ff9bc5b
[efs]: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdpefs/34d9de58-b2b5-40b6-b970-f82d4603bdb5
[ecam]: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdpecam/92af6790-b79c-4813-9c07-7c545bed0242
[eai]: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdpeai/d04ffa42-5a0f-4f80-abb1-cc26f71c9452
