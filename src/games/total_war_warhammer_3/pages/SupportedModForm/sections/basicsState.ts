/** State held by the Basics section. */
export interface BasicsState {
    name: string
    package_name: string
    workshop_id: string
    /** The user supplies `path` directly. */
    custom_path: boolean
    /** Only meaningful when `custom_path` is true. */
    path: string
}

/** Default empty state for a fresh form. */
export const emptyBasicsState: BasicsState = {
    name: "",
    package_name: "",
    workshop_id: "",
    custom_path: false,
    path: "",
}
