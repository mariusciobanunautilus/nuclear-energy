export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.15"
  }
  public: {
    Tables: {
      countries: {
        Row: {
          created_at: string
          has_commercial_nuclear: boolean
          id: string
          iso2: string
          iso3: string
          name: string
          region: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          has_commercial_nuclear?: boolean
          id?: string
          iso2: string
          iso3: string
          name: string
          region: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          has_commercial_nuclear?: boolean
          id?: string
          iso2?: string
          iso3?: string
          name?: string
          region?: string
          updated_at?: string
        }
        Relationships: []
      }
      country_generation_years: {
        Row: {
          country_id: string
          created_at: string
          id: string
          nuclear_generation_twh: number | null
          nuclear_share_percent: number | null
          reactors_operable: number | null
          source_id: string | null
          updated_at: string
          year: number
        }
        Insert: {
          country_id: string
          created_at?: string
          id?: string
          nuclear_generation_twh?: number | null
          nuclear_share_percent?: number | null
          reactors_operable?: number | null
          source_id?: string | null
          updated_at?: string
          year: number
        }
        Update: {
          country_id?: string
          created_at?: string
          id?: string
          nuclear_generation_twh?: number | null
          nuclear_share_percent?: number | null
          reactors_operable?: number | null
          source_id?: string | null
          updated_at?: string
          year?: number
        }
        Relationships: [
          {
            foreignKeyName: "country_generation_years_country_id_fkey"
            columns: ["country_id"]
            isOneToOne: false
            referencedRelation: "countries"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "country_generation_years_source_id_fkey"
            columns: ["source_id"]
            isOneToOne: false
            referencedRelation: "source_documents"
            referencedColumns: ["id"]
          },
        ]
      }
      fuel_cycle_facilities: {
        Row: {
          annual_capacity: string | null
          country_id: string
          created_at: string
          id: string
          locality: string | null
          name: string
          notes: string | null
          operator: string | null
          source_id: string | null
          status: string
          type: Database["public"]["Enums"]["facility_type"]
          updated_at: string
        }
        Insert: {
          annual_capacity?: string | null
          country_id: string
          created_at?: string
          id?: string
          locality?: string | null
          name: string
          notes?: string | null
          operator?: string | null
          source_id?: string | null
          status?: string
          type: Database["public"]["Enums"]["facility_type"]
          updated_at?: string
        }
        Update: {
          annual_capacity?: string | null
          country_id?: string
          created_at?: string
          id?: string
          locality?: string | null
          name?: string
          notes?: string | null
          operator?: string | null
          source_id?: string | null
          status?: string
          type?: Database["public"]["Enums"]["facility_type"]
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "fuel_cycle_facilities_country_id_fkey"
            columns: ["country_id"]
            isOneToOne: false
            referencedRelation: "countries"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "fuel_cycle_facilities_source_id_fkey"
            columns: ["source_id"]
            isOneToOne: false
            referencedRelation: "source_documents"
            referencedColumns: ["id"]
          },
        ]
      }
      power_plants: {
        Row: {
          country_id: string
          created_at: string
          id: string
          latitude: number | null
          locality: string | null
          longitude: number | null
          name: string
          operator: string | null
          owner: string | null
          source_id: string | null
          updated_at: string
        }
        Insert: {
          country_id: string
          created_at?: string
          id?: string
          latitude?: number | null
          locality?: string | null
          longitude?: number | null
          name: string
          operator?: string | null
          owner?: string | null
          source_id?: string | null
          updated_at?: string
        }
        Update: {
          country_id?: string
          created_at?: string
          id?: string
          latitude?: number | null
          locality?: string | null
          longitude?: number | null
          name?: string
          operator?: string | null
          owner?: string | null
          source_id?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "power_plants_country_id_fkey"
            columns: ["country_id"]
            isOneToOne: false
            referencedRelation: "countries"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "power_plants_source_id_fkey"
            columns: ["source_id"]
            isOneToOne: false
            referencedRelation: "source_documents"
            referencedColumns: ["id"]
          },
        ]
      }
      reactor_sources: {
        Row: {
          created_at: string
          note: string | null
          reactor_id: string
          source_id: string
        }
        Insert: {
          created_at?: string
          note?: string | null
          reactor_id: string
          source_id: string
        }
        Update: {
          created_at?: string
          note?: string | null
          reactor_id?: string
          source_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "reactor_sources_reactor_id_fkey"
            columns: ["reactor_id"]
            isOneToOne: false
            referencedRelation: "reactors"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "reactor_sources_source_id_fkey"
            columns: ["source_id"]
            isOneToOne: false
            referencedRelation: "source_documents"
            referencedColumns: ["id"]
          },
        ]
      }
      reactor_technologies: {
        Row: {
          code: string
          coolant: string | null
          created_at: string
          id: string
          moderator: string | null
          name: string
          neutron_spectrum: string
          notes: string | null
          updated_at: string
        }
        Insert: {
          code: string
          coolant?: string | null
          created_at?: string
          id?: string
          moderator?: string | null
          name: string
          neutron_spectrum?: string
          notes?: string | null
          updated_at?: string
        }
        Update: {
          code?: string
          coolant?: string | null
          created_at?: string
          id?: string
          moderator?: string | null
          name?: string
          neutron_spectrum?: string
          notes?: string | null
          updated_at?: string
        }
        Relationships: []
      }
      reactors: {
        Row: {
          commercial_operation_on: string | null
          construction_started_on: string | null
          created_at: string
          grid_connected_on: string | null
          gross_capacity_mwe: number | null
          id: string
          name: string
          net_capacity_mwe: number | null
          notes: string | null
          plant_id: string
          shutdown_on: string | null
          source_id: string | null
          status: Database["public"]["Enums"]["reactor_status"]
          technology_id: string | null
          updated_at: string
        }
        Insert: {
          commercial_operation_on?: string | null
          construction_started_on?: string | null
          created_at?: string
          grid_connected_on?: string | null
          gross_capacity_mwe?: number | null
          id?: string
          name: string
          net_capacity_mwe?: number | null
          notes?: string | null
          plant_id: string
          shutdown_on?: string | null
          source_id?: string | null
          status: Database["public"]["Enums"]["reactor_status"]
          technology_id?: string | null
          updated_at?: string
        }
        Update: {
          commercial_operation_on?: string | null
          construction_started_on?: string | null
          created_at?: string
          grid_connected_on?: string | null
          gross_capacity_mwe?: number | null
          id?: string
          name?: string
          net_capacity_mwe?: number | null
          notes?: string | null
          plant_id?: string
          shutdown_on?: string | null
          source_id?: string | null
          status?: Database["public"]["Enums"]["reactor_status"]
          technology_id?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "reactors_plant_id_fkey"
            columns: ["plant_id"]
            isOneToOne: false
            referencedRelation: "power_plants"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "reactors_source_id_fkey"
            columns: ["source_id"]
            isOneToOne: false
            referencedRelation: "source_documents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "reactors_technology_id_fkey"
            columns: ["technology_id"]
            isOneToOne: false
            referencedRelation: "reactor_technologies"
            referencedColumns: ["id"]
          },
        ]
      }
      safety_events: {
        Row: {
          country_id: string | null
          created_at: string
          event_date: string
          id: string
          ines_level: number | null
          reactor_id: string | null
          severity: Database["public"]["Enums"]["incident_severity"]
          source_id: string | null
          summary: string | null
          title: string
          updated_at: string
        }
        Insert: {
          country_id?: string | null
          created_at?: string
          event_date: string
          id?: string
          ines_level?: number | null
          reactor_id?: string | null
          severity?: Database["public"]["Enums"]["incident_severity"]
          source_id?: string | null
          summary?: string | null
          title: string
          updated_at?: string
        }
        Update: {
          country_id?: string | null
          created_at?: string
          event_date?: string
          id?: string
          ines_level?: number | null
          reactor_id?: string | null
          severity?: Database["public"]["Enums"]["incident_severity"]
          source_id?: string | null
          summary?: string | null
          title?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "safety_events_country_id_fkey"
            columns: ["country_id"]
            isOneToOne: false
            referencedRelation: "countries"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "safety_events_reactor_id_fkey"
            columns: ["reactor_id"]
            isOneToOne: false
            referencedRelation: "reactors"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "safety_events_source_id_fkey"
            columns: ["source_id"]
            isOneToOne: false
            referencedRelation: "source_documents"
            referencedColumns: ["id"]
          },
        ]
      }
      source_documents: {
        Row: {
          accessed_on: string
          created_at: string
          id: string
          notes: string | null
          published_on: string | null
          publisher: string | null
          title: string
          updated_at: string
          url: string | null
        }
        Insert: {
          accessed_on?: string
          created_at?: string
          id?: string
          notes?: string | null
          published_on?: string | null
          publisher?: string | null
          title: string
          updated_at?: string
          url?: string | null
        }
        Update: {
          accessed_on?: string
          created_at?: string
          id?: string
          notes?: string | null
          published_on?: string | null
          publisher?: string | null
          title?: string
          updated_at?: string
          url?: string | null
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      facility_type:
        | "uranium_mine"
        | "conversion"
        | "enrichment"
        | "fuel_fabrication"
        | "research"
        | "storage"
        | "reprocessing"
        | "waste_repository"
      incident_severity: "info" | "low" | "medium" | "high" | "severe"
      reactor_status:
        | "planned"
        | "under_construction"
        | "operational"
        | "suspended"
        | "shutdown"
        | "decommissioning"
        | "decommissioned"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      facility_type: [
        "uranium_mine",
        "conversion",
        "enrichment",
        "fuel_fabrication",
        "research",
        "storage",
        "reprocessing",
        "waste_repository",
      ],
      incident_severity: ["info", "low", "medium", "high", "severe"],
      reactor_status: [
        "planned",
        "under_construction",
        "operational",
        "suspended",
        "shutdown",
        "decommissioning",
        "decommissioned",
      ],
    },
  },
} as const
