/**
 * Describe how many translations a glossary rename updated, worded like the suggestion review.
 * @param english - New English.
 * @param replaced - Translations changed.
 * @returns The notice.
 */
export function renameNotice(english: string, replaced: number): string {
    return `${english}: updated ${replaced} translation${replaced === 1 ? "" : "s"}.`
}
